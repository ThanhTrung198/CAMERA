import { cn } from "@/lib/utils";
import { WifiOff, CameraOff } from "lucide-react";
import { useEffect, useState } from "react";
// Đảm bảo đường dẫn này đúng với nơi anh lưu file api.ts
// Nếu anh để ở client/src/lib/api.ts thì import là: "@/lib/api"
import { API_URLS } from "../../../service/api";

interface CameraFeedProps {
  src?: string;
  label: string;
  location: string;
  status?: "live" | "offline" | "recording";
  className?: string;
  useWebcam?: boolean;
  camId?: number;
}

export default function CameraFeed({
  src,
  label,
  location,
  status = "live",
  className,
  useWebcam = false,
  camId = 0,
}: CameraFeedProps) {
  const [time, setTime] = useState(new Date());
  const [imgSrc, setImgSrc] = useState<string | undefined>(src);
  const [hasError, setHasError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // Cập nhật đồng hồ và auto-retry mỗi 5 giây nếu có lỗi
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
      // Auto retry nếu có lỗi
      if (hasError && retryCount < 10) {
        setRetryCount(prev => prev + 1);
        setHasError(false);
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [hasError, retryCount]);

  // Cập nhật nguồn ảnh với timestamp để tránh cache
  useEffect(() => {
    setHasError(false);
    let newSrc: string;

    if (useWebcam && status !== "offline") {
      newSrc = API_URLS.STREAM(camId);
    } else {
      newSrc = src || "";
    }

    // Thêm timestamp để buộc reload
    if (newSrc && !newSrc.includes("?")) {
      setImgSrc(`${newSrc}?t=${Date.now()}`);
    } else {
      setImgSrc(newSrc);
    }
  }, [useWebcam, status, camId, src, retryCount]);

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg border bg-black group",
        className
      )}
    >
      {/* Video Feed Layer */}
      <div className="aspect-video w-full relative bg-zinc-950">
        {/* Logic hiển thị: Nếu Offline HOẶC có lỗi tải ảnh -> Hiện màn hình chờ */}
        {status === "offline" || hasError ? (
          <div className="w-full h-full flex items-center justify-center bg-zinc-900/50">
            <div className="text-zinc-600 flex flex-col items-center gap-2">
              {status === "offline" ? (
                <WifiOff className="h-10 w-10 opacity-50" />
              ) : (
                <CameraOff className="h-10 w-10 opacity-50" />
              )}
              <span className="font-mono text-xs tracking-wider opacity-70">
                {status === "offline" ? "MẤT TÍN HIỆU" : "KHÔNG TÌM THẤY VIDEO"}
              </span>
            </div>
          </div>
        ) : (
          // Hiển thị Stream
          <img
            src={imgSrc}
            alt={`Camera feed from ${label}`}
            className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity duration-300"
            onError={() => setHasError(true)} // Nếu backend chưa bật, chuyển sang giao diện lỗi
          />
        )}

        {/* Scanline Effect (Hiệu ứng quét) */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] z-10 bg-[length:100%_2px,3px_100%] pointer-events-none" />

        {/* Vignette (Tối 4 góc) */}
        <div className="absolute inset-0 bg-[radial-gradient(circle,transparent_50%,black_100%)] opacity-60 pointer-events-none" />
      </div>

      {/* Overlay UI (Thông tin camera) */}
      <div className="absolute inset-0 p-4 flex flex-col justify-between z-20 pointer-events-none">
        {/* Header Overlay */}
        <div className="flex justify-between items-start">
          <div className="bg-black/60 backdrop-blur-md px-2 py-1 rounded border border-white/10 shadow-sm">
            <div className="text-[10px] font-bold text-emerald-500 font-mono tracking-wider">
              {label}
            </div>
            <div className="text-[9px] text-zinc-400 font-sans">{location}</div>
          </div>

          <div className="flex items-center gap-2">
            {status === "live" && !hasError && (
              <div className="bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded flex items-center gap-1.5 backdrop-blur-sm">
                <div className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[9px] font-bold text-red-500 font-mono tracking-widest">
                  REC
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Footer Overlay */}
        <div className="flex justify-between items-end text-[10px] font-mono text-zinc-400/80">
          <div className="flex gap-3">
            <span>FPS: {useWebcam && !hasError ? "30.0" : "--"}</span>
            <span>ID: {camId}</span>
          </div>
          <div>{time.toLocaleTimeString("en-US", { hour12: false })}</div>
        </div>
      </div>
    </div>
  );
}
