import cv2
import numpy as np
import torch
import os

def detect_green_crop_bounds(first_frame, padding=20):
    """Detects the green screen bounds on frame 1 to eliminate non-green room background."""
    hsv = cv2.cvtColor(first_frame, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([85, 255, 255])
    
    mask = cv2.inRange(hsv, lower_green, upper_green)
    coords = cv2.findNonZero(mask)
    
    if coords is None:
        raise ValueError("No green screen detected in initial frame.")
        
    x, y, w, h = cv2.boundingRect(coords)
    
    ymin = max(0, y - padding)
    ymax = min(first_frame.shape[0], y + h + padding)
    xmin = max(0, x - padding)
    xmax = min(first_frame.shape[1], x + w + padding)
    
    return ymin, ymax, xmin, xmax

def run_m1_alpha_pipeline(input_path, output_path):
    if not torch.backends.mps.is_available():
        raise SystemError("Apple Silicon MPS acceleration is not active.")
        
    device = torch.device("mps")
    print(f"Loading RVM Model onto Apple Silicon ({device})...")
    
    # Load RVM MobileNetV3 variant for lowest memory footprint
    model = torch.hub.load("PeterL1n/RobustVideoMatting", "mobilenetv3", trust_repo=True).to(device).eval()
    
    cap = cv2.VideoCapture(input_path)
    ret, first_frame = cap.read()
    if not ret:
        print("Error reading source clip.")
        return

    # Calculate static crop bounds from first frame
    ymin, ymax, xmin, xmax = detect_green_crop_bounds(first_frame)
    crop_w, crop_h = (xmax - xmin), (ymax - ymin)
    print(f"Crop coordinates locked: Y[{ymin}:{ymax}] X[{xmin}:{xmax}] | Frame: {crop_w}x{crop_h}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (crop_w, crop_h))

    rec = [None] * 4  # RVM Recurrent States
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Reset video to start

    with torch.no_grad():
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Crop to green backdrop boundaries
            cropped = frame[ymin:ymax, xmin:xmax]
            
            # Prepare tensor for MPS execution
            rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
            src = torch.from_numpy(rgb).float().permute(2, 0, 1).unsqueeze(0).div(255).to(device)
            
            # Execute RVM matting step
            fgr, pha, *rec = model(src, *rec, downsample_ratio=0.25)
            
            # Export 8-bit single-channel black & white alpha mask
            alpha = (pha.squeeze().cpu().numpy() * 255).astype(np.uint8)
            alpha_bgr = cv2.cvtColor(alpha, cv2.COLOR_GRAY2BGR)
            out.write(alpha_bgr)

    cap.release()
    out.release()
    print(f"Render Complete! Alpha matte saved to: {output_path}")

if __name__ == "__main__":
    run_m1_alpha_pipeline("2025-09-28-07-57.mp4", "output_alpha.mp4")
