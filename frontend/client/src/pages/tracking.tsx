import React, { useState, useEffect, useRef } from "react";
import Layout from "@/components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Users,
    Video,
    Target,
    AlertTriangle,
    Trash2,
    Circle,
    Square,
} from "lucide-react";

// Tracking Stats Card
const StatsCard = ({ title, value, icon: Icon, description, alert = false }: any) => (
    <Card className={`${alert ? "border-red-500 bg-red-500/5" : ""}`}>
        <CardContent className="p-4">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm text-muted-foreground">{title}</p>
                    <p className={`text-2xl font-bold ${alert ? "text-red-500" : ""}`}>{value}</p>
                    <p className="text-xs text-muted-foreground mt-1">{description}</p>
                </div>
                <div className={`p-3 rounded-full ${alert ? "bg-red-500/10" : "bg-primary/10"}`}>
                    <Icon className={`h-6 w-6 ${alert ? "text-red-500" : "text-primary"}`} />
                </div>
            </div>
        </CardContent>
    </Card>
);

// Camera Panel Component
const CameraPanel = ({ camIndex, camLabel, ipAddress, stats }: any) => {
    const [isDrawing, setIsDrawing] = useState(false);
    const [points, setPoints] = useState<{ x: number; y: number }[]>([]);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Handle zone drawing
    const handleCanvasClick = (e: React.MouseEvent) => {
        if (!isDrawing) return;
        const rect = (e.target as HTMLElement).getBoundingClientRect();
        const x = Math.round(((e.clientX - rect.left) / rect.width) * 640);
        const y = Math.round(((e.clientY - rect.top) / rect.height) * 480);
        setPoints([...points, { x, y }]);
    };

    // Save zone
    const saveZone = async () => {
        if (points.length < 3) {
            alert("Zone cần ít nhất 3 điểm!");
            return;
        }
        try {
            const res = await fetch("http://localhost:5000/api/tracking/zones", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ points, camera_id: camIndex }),
            });
            const data = await res.json();
            if (data.success) {
                alert("Đã thêm zone thành công!");
                setPoints([]);
                setIsDrawing(false);
            } else {
                alert("Lỗi: " + data.message);
            }
        } catch (error: any) {
            alert("Lỗi kết nối: " + error.message);
        }
    };

    // Clear zones for this camera
    const clearZones = async () => {
        if (!confirm(`Xóa tất cả zones của ${camLabel}?`)) return;
        try {
            await fetch(`http://localhost:5000/api/tracking/zones?camera_id=${camIndex}`, {
                method: "DELETE",
            });
            setPoints([]);
            setIsDrawing(false);
        } catch (error) {
            console.error("Error clearing zones:", error);
        }
    };

    // Draw points on canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (points.length > 0) {
            ctx.fillStyle = "rgba(255, 0, 0, 0.3)";
            ctx.strokeStyle = "red";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            points.forEach((p) => ctx.lineTo(p.x, p.y));
            ctx.closePath();
            ctx.fill();
            ctx.stroke();

            points.forEach((p, i) => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, 5, 0, 2 * Math.PI);
                ctx.fillStyle = "red";
                ctx.fill();
                ctx.fillStyle = "white";
                ctx.font = "12px Arial";
                ctx.fillText(String(i + 1), p.x + 8, p.y + 4);
            });
        }
    }, [points]);

    return (
        <Card>
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Video className="h-5 w-5" />
                        {camLabel}
                        {ipAddress && (
                            <Badge variant="outline" className="ml-1 text-xs">{ipAddress}</Badge>
                        )}
                    </CardTitle>
                    <div className="flex gap-1.5 flex-wrap">
                        {!isDrawing ? (
                            <Button
                                size="sm"
                                onClick={() => setIsDrawing(true)}
                                variant="outline"
                                className="bg-green-500/10 border-green-500 text-green-500 hover:bg-green-500/20"
                            >
                                <Target className="h-4 w-4 mr-1" /> Vẽ Zone
                            </Button>
                        ) : (
                            <>
                                <Button
                                    size="sm"
                                    onClick={saveZone}
                                    disabled={points.length < 3}
                                    className="bg-blue-500 hover:bg-blue-600"
                                >
                                    <Square className="h-4 w-4 mr-1" /> Lưu ({points.length})
                                </Button>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => { setPoints([]); setIsDrawing(false); }}
                                >
                                    Hủy
                                </Button>
                            </>
                        )}
                        <Button size="sm" variant="destructive" onClick={clearZones}>
                            <Trash2 className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
                {isDrawing && (
                    <p className="text-sm text-yellow-500 mt-2">
                        ⚠️ Click vào video để đánh dấu các điểm zone (ít nhất 3 điểm)
                    </p>
                )}
            </CardHeader>
            <CardContent className="p-2">
                <div
                    className={`relative aspect-video bg-black rounded-lg overflow-hidden ${isDrawing ? "cursor-crosshair ring-2 ring-red-500" : ""}`}
                    onClick={handleCanvasClick}
                >
                    <img
                        src={`http://localhost:5000/video_feed/${camIndex}?t=${Date.now()}`}
                        alt={`${camLabel} Feed`}
                        className="w-full h-full object-contain"
                        onError={(e) => {
                            setTimeout(() => {
                                (e.target as HTMLImageElement).src = `http://localhost:5000/video_feed/${camIndex}?t=${Date.now()}`;
                            }, 2000);
                        }}
                    />

                    {/* Canvas vẽ zone */}
                    <canvas
                        ref={canvasRef}
                        width={640}
                        height={480}
                        className="absolute inset-0 w-full h-full"
                        style={{ pointerEvents: "none" }}
                    />

                    {/* Drawing mode */}
                    {isDrawing && (
                        <div className="absolute top-2 left-2 bg-red-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium animate-pulse">
                            🎯 Vẽ Zone - Click thêm điểm ({points.length})
                        </div>
                    )}

                    {/* Info overlay */}
                    <div className="absolute bottom-2 left-2 bg-black/70 text-white px-2 py-1 rounded text-xs">
                        Zones: {stats.zones_count} | Tracking: {stats.current_active} người
                    </div>

                    {/* LIVE indicator */}
                    <div className="absolute top-2 right-2">
                        <div className="bg-black/70 text-white px-2 py-1 rounded text-xs flex items-center gap-1">
                            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
                            LIVE
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default function Tracking() {
    const [stats, setStats] = useState({
        tracking_enabled: false,
        total_unique_people: 0,
        current_active: 0,
        zones_count: 0,
        is_recording: false,
        total_recordings: 0,
        total_intruders_recorded: 0,
        recording_duration: 0,
    });

    // Fetch stats
    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await fetch("http://localhost:5000/api/tracking/stats");
                const data = await res.json();
                setStats(data);
            } catch (error) {
                console.error("Error fetching tracking stats:", error);
            }
        };

        fetchStats();
        const interval = setInterval(fetchStats, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <Layout>
            <div className="flex flex-col gap-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-3xl font-bold tracking-tight">
                            Tracking & Zone
                        </h2>
                        <p className="text-muted-foreground">
                            Theo dõi người & phát hiện xâm nhập thời gian thực — 2 Camera
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {stats.is_recording && (
                            <Badge variant="destructive" className="animate-pulse">
                                <Circle className="h-2 w-2 mr-1 fill-current" /> REC
                            </Badge>
                        )}
                        <Badge variant={stats.tracking_enabled ? "default" : "secondary"}>
                            {stats.tracking_enabled ? "TRACKING ON" : "TRACKING OFF"}
                        </Badge>
                    </div>
                </div>

                {/* Stats Cards */}
                <div className="grid gap-4 md:grid-cols-4">
                    <StatsCard
                        title="Đang Tracking"
                        value={stats.current_active}
                        icon={Users}
                        description={`Tổng phát hiện: ${stats.total_unique_people}`}
                    />
                    <StatsCard
                        title="Zones Đã Vẽ"
                        value={stats.zones_count}
                        icon={Target}
                        description="Vùng phát hiện xâm nhập"
                    />
                    <StatsCard
                        title="Intrusion Events"
                        value={stats.total_recordings}
                        icon={AlertTriangle}
                        description={`${stats.total_intruders_recorded} người đã phát hiện`}
                        alert={stats.is_recording}
                    />
                    <StatsCard
                        title="Trạng thái"
                        value={stats.is_recording ? "RECORDING" : "Standby"}
                        icon={Video}
                        description={
                            stats.is_recording
                                ? `Đang ghi: ${stats.recording_duration?.toFixed(1)}s`
                                : "Chờ xâm nhập"
                        }
                        alert={stats.is_recording}
                    />
                </div>

                {/* Dual Camera View */}
                <div className="grid gap-4 lg:grid-cols-2">
                    <CameraPanel
                        camIndex={0}
                        camLabel="CAM 1 — Webcam"
                        ipAddress={null}
                        stats={stats}
                    />
                    <CameraPanel
                        camIndex={0 }
                        camLabel="CAM 2 — Webcam"
                        ipAddress={null}
                        stats={stats}
                    />
                </div>
            </div>
        </Layout>
    );
}
