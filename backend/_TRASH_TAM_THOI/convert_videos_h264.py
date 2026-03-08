"""
Script chuyển đổi video cũ (mp4v/FMP4) sang H.264 (browser-compatible)
KHÔNG xóa file gốc - chỉ tạo file mới và rename
"""
import cv2
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

VIDEO_DIR = Path(__file__).parent / "intrusion_recordings"
BACKUP_DIR = VIDEO_DIR / "_backup_mp4v"

def convert_video(input_path, output_path):
    """Chuyển đổi video từ mp4v sang H.264 qua MSMF"""
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        return False, "Cannot open input"
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if total_frames == 0 or w == 0 or h == 0:
        cap.release()
        return False, f"Invalid video: {total_frames} frames, {w}x{h}"
    
    fourcc = cv2.VideoWriter_fourcc(*'H264')
    writer = cv2.VideoWriter(str(output_path), cv2.CAP_MSMF, fourcc, fps, (w, h))
    
    if not writer.isOpened():
        cap.release()
        return False, "Cannot create H264 writer"
    
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)
        count += 1
        if count % 100 == 0:
            print(f"  Progress: {count}/{total_frames} frames")
    
    writer.release()
    cap.release()
    
    return True, f"Converted {count} frames"

def main():
    if not VIDEO_DIR.exists():
        print("Video directory not found!")
        return
    
    # Tạo backup dir
    BACKUP_DIR.mkdir(exist_ok=True)
    
    mp4_files = sorted(VIDEO_DIR.glob("*.mp4"))
    print(f"Found {len(mp4_files)} video files")
    
    converted = 0
    skipped = 0
    failed = 0
    
    for vf in mp4_files:
        size = vf.stat().st_size
        
        # Skip corrupted/empty files
        if size < 1024:
            print(f"SKIP (empty): {vf.name} ({size} bytes)")
            skipped += 1
            continue
        
        # Check if already H.264
        cap = cv2.VideoCapture(str(vf))
        if not cap.isOpened():
            print(f"SKIP (cant open): {vf.name}")
            skipped += 1
            continue
        
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = chr(fourcc & 0xFF) + chr((fourcc >> 8) & 0xFF) + chr((fourcc >> 16) & 0xFF) + chr((fourcc >> 24) & 0xFF)
        cap.release()
        
        if codec.lower() == 'h264' or codec.lower() == 'avc1':
            print(f"SKIP (already H264): {vf.name}")
            skipped += 1
            continue
        
        print(f"\nCONVERT: {vf.name} (codec: {codec}, {round(size/1024/1024,2)}MB)")
        
        # Convert to temp file
        temp_path = vf.parent / f"_converting_{vf.name}"
        success, msg = convert_video(vf, temp_path)
        
        if success:
            # Backup original
            backup_path = BACKUP_DIR / vf.name
            shutil.move(str(vf), str(backup_path))
            # Move converted to original name
            shutil.move(str(temp_path), str(vf))
            new_size = vf.stat().st_size
            print(f"  OK: {msg} | {round(size/1024/1024,2)}MB -> {round(new_size/1024/1024,2)}MB")
            converted += 1
        else:
            print(f"  FAILED: {msg}")
            if temp_path.exists():
                temp_path.unlink()
            failed += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"Converted: {converted}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print(f"Backups:   {BACKUP_DIR}")

if __name__ == "__main__":
    main()
