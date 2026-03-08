import React, { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import StatusCard from "@/components/StatusCard";
import {
  Users,
  DoorClosed,
  AlertTriangle,
  Activity,
  CheckCircle,
  ShieldAlert,
  Video, // [MỚI] Icon cho CameraFeed
  VideoOff, // [MỚI] Icon cho CameraFeed
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// --- COMPONENT CAMERA FEED (Được tích hợp vào đây) ---
const CameraFeed = ({
  src,
  label,
  location,
  status = "live",
  useWebcam = false,
}) => {
  const [error, setError] = useState(false);

  return (
    <Card className="overflow-hidden border-l-4 border-l-emerald-500 shadow-sm hover:shadow-md transition-shadow">
      <CardHeader className="p-3 bg-muted/20 pb-2">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Video className="h-4 w-4 text-emerald-600" />
            <span className="font-semibold text-sm">{label}</span>
          </div>
          <Badge
            variant={status === "live" ? "default" : "destructive"}
            className="text-[10px] px-2 h-5"
          >
            {status === "live" ? "TRỰC TUYẾN" : "MẤT TÍN HIỆU"}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground ml-6">{location}</p>
      </CardHeader>

      <CardContent className="p-0 relative aspect-video bg-black flex items-center justify-center">
        {!error ? (
          /* ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT: Thẻ IMG trỏ thẳng vào link Python */
          <img
            src={src}
            alt={label}
            className="w-full h-full object-cover"
            onError={() => setError(true)}
            loading="lazy"
          />
        ) : (
          <div className="flex flex-col items-center text-muted-foreground gap-2">
            <VideoOff className="h-8 w-8 opacity-50" />
            <span className="text-xs">Không thể kết nối camera</span>
          </div>
        )}

        {/* Overlay hiệu ứng REC */}
        <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/50 px-2 py-0.5 rounded text-[10px] text-white backdrop-blur-sm">
          <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse"></div>
          REC
        </div>
      </CardContent>
    </Card>
  );
};

// --- DỮ LIỆU MẪU CHO BIỂU ĐỒ ---
const initialChartData = [
  { time: "10:00:00", visits: 45 },
  { time: "10:00:05", visits: 52 },
  { time: "10:00:10", visits: 38 },
  { time: "10:00:15", visits: 65 },
  { time: "10:00:20", visits: 48 },
  { time: "10:00:25", visits: 60 },
  { time: "10:00:30", visits: 55 },
];

// --- MAIN DASHBOARD COMPONENT ---
export default function Dashboard() {
  const [chartData, setChartData] = useState(initialChartData);

  // State Logs
  const [logs, setLogs] = useState([]);

  const [gpuLoad, setGpuLoad] = useState(0);
  const [temp, setTemp] = useState(40);

  // --- STATE QUẢN LÝ NHÂN SỰ ---
  const [presentCount, setPresentCount] = useState(0);
  const [totalEmployees, setTotalEmployees] = useState(0);

  // --- STATE CẢNH BÁO AN NINH ---
  const [warningCount, setWarningCount] = useState(0);

  // --- LOGIC MỚI: GỌI API THAY VÌ RANDOM ---
  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        // Gọi API Python
        const res = await fetch("http://localhost:5000/api/dashboard-stats");
        const data = await res.json();

        // 1. Cập nhật số liệu từ Python
        setPresentCount(data.present_count);
        setTotalEmployees(data.total_employees);

        // 2. Cập nhật số lượng cảnh báo
        setWarningCount(data.warning_count);

        setLogs(data.logs); // Log thật từ camera
        setGpuLoad(data.gpu_load);
        setTemp(data.temp);

        // 3. Cập nhật biểu đồ (Vẫn giữ logic chạy theo thời gian thực)
        const now = new Date();
        const timeString = now.toLocaleTimeString("vi-VN", { hour12: false });

        setChartData((prevData) => {
          // Lấy số liệu thực tế làm dữ liệu cho biểu đồ
          const currentVisits = data.present_count;

          const newData = [
            ...prevData.slice(1),
            { time: timeString, visits: currentVisits },
          ];
          return newData;
        });
      } catch (error) {
        console.error("Lỗi kết nối tới Server Python:", error);
      }
    };

    // Gọi ngay lập tức lần đầu
    fetchDashboardData();

    // Thiết lập vòng lặp gọi API mỗi 1 giây (1000ms) để phản ứng NHANH
    const interval = setInterval(fetchDashboardData, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <h2 className="text-3xl font-bold tracking-tight">
            Trung tâm Giám sát AI
          </h2>
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <span className="text-sm text-muted-foreground font-mono">
              SYSTEM ONLINE
            </span>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatusCard
            title="Nhân sự hiện diện"
            value={`${presentCount}/${totalEmployees}`}
            icon={Users}
            description="Tỷ lệ đi làm hôm nay"
            trend={
              totalEmployees > 0 && presentCount / totalEmployees > 0.8
                ? "up"
                : "neutral"
            }
            trendValue={
              totalEmployees > 0
                ? `${((presentCount / totalEmployees) * 100).toFixed(1)}%`
                : "0%"
            }
          />

          {/* --- THẺ CẢNH BÁO AN NINH --- */}
          <StatusCard
            title={
              warningCount > 0 ? "CẢNH BÁO XÂM NHẬP" : "Trạng thái an ninh"
            }
            value={warningCount > 0 ? `${warningCount} ĐỐI TƯỢNG` : "An toàn"}
            icon={warningCount > 0 ? AlertTriangle : CheckCircle}
            description={
              warningCount > 0 ? "Phát hiện người lạ mặt!" : "Khu vực an toàn"
            }
            alert={warningCount > 0}
          />

          <StatusCard
            title="Trạng thái Cửa từ"
            value="Đã khóa"
            icon={DoorClosed}
            description="Khu vực Server & Kho"
            trend="neutral"
            trendValue="An toàn"
          />
          <StatusCard
            title="Tải GPU xử lý"
            value={`${gpuLoad}%`}
            icon={Activity}
            description={`Nhiệt độ: ${temp}°C`}
            trend={gpuLoad > 80 ? "down" : "neutral"}
            trendValue="Real-time"
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
          {/* Attendance Chart */}
          <Card className="col-span-4">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Lưu lượng theo thời gian thực</span>
                <Badge
                  variant="outline"
                  className="font-mono font-normal animate-pulse text-emerald-500 border-emerald-500"
                >
                  LIVE UPDATING
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="pl-2">
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient
                        id="colorVisits"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="5%"
                          stopColor="hsl(var(--primary))"
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="95%"
                          stopColor="hsl(var(--primary))"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border))"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="time"
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `${value}`}
                      domain={[0, 100]}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        borderColor: "hsl(var(--border))",
                        borderRadius: "6px",
                        color: "hsl(var(--foreground))",
                      }}
                      itemStyle={{ color: "hsl(var(--primary))" }}
                    />
                    <Area
                      type="monotone"
                      dataKey="visits"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorVisits)"
                      isAnimationActive={true}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Live Feeds */}
          <div className="col-span-3 space-y-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm text-muted-foreground">
                Camera AI (Real-time)
              </h3>
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 text-primary"
              >
                Cấu hình
              </Button>
            </div>

            {/* --- PHẦN CHỈNH SỬA KẾT NỐI CAMERA --- */}
            <div className="grid gap-4">
              <div className="grid gap-4">
                {/* CAMERA 1: WEBCAM LAPTOP (Stream từ Python port 5000) */}
                <CameraFeed
                  useWebcam={false}
                  src="http://localhost:5000/video_feed/0"
                  label="CAM-01:Sảnh chính"
                  location="Sảnh Chính"
                  status="live"
                />

                {/* CAMERA 2: USB CAMERA (Stream từ Python port 5000) */}
                <CameraFeed
                  useWebcam={false}
                  src="http://localhost:5000/video_feed/1"
                  label="CAM-02"
                  location="Khu vực hạn chế ra vào"
                  status="live"
                />
              </div>
            </div>
            {/* --- HẾT PHẦN CHỈNH SỬA --- */}
          </div>
        </div>

        {/* Recent Logs Table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex justify-between items-center">
              <span>Nhật ký nhận diện (Live Feed)</span>
              <span className="text-xs font-normal text-muted-foreground bg-secondary px-2 py-1 rounded-full">
                {logs.length} events
              </span>
            </CardTitle>
          </CardHeader>

          <CardContent>
            {/* --- KHỐI CẢNH BÁO PHỤ DƯỚI TIÊU ĐỀ --- */}
            {warningCount > 0 && (
              <div className="mb-4 p-3 rounded-lg border border-red-500/50 bg-red-500/10 text-red-500 flex items-center gap-3 animate-pulse shadow-sm">
                <div className="p-2 bg-red-500/20 rounded-full">
                  <ShieldAlert className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-bold text-sm">PHÁT HIỆN XÂM NHẬP!</p>
                  <p className="text-xs opacity-90">
                    Hệ thống đang theo dõi{" "}
                    <span className="font-bold text-base">{warningCount}</span>{" "}
                    đối tượng lạ mặt.
                  </p>
                </div>
              </div>
            )}

            <div className="space-y-4">
              {logs.map((log, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0 animate-in slide-in-from-left-2 duration-300"
                >
                  <div className="flex items-center gap-4">
                    <div className="h-9 w-9 rounded-full bg-muted flex items-center justify-center">
                      <Users className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">
                        {log.name}{" "}
                        <span className="text-xs text-muted-foreground">
                          ({log.id})
                        </span>
                      </p>
                      <p className="text-xs text-muted-foreground">{log.loc}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <Badge
                      variant="outline"
                      className={
                        log.status === "Cảnh báo"
                          ? "bg-red-500/10 text-red-500 border-red-500/20"
                          : "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                      }
                    >
                      {log.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground font-mono">
                      {log.time}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
