
import React, { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import {
  Users,
  DoorClosed,
  AlertTriangle,
  Activity,
  CheckCircle,
  ShieldAlert,
  Video,
  VideoOff,
  ChevronRight,
  Settings,
  Download,
  TrendingUp,
  Eye,
  Clock,
  Filter,
  ChevronDown,
  X,
  Search,
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

// --- COMPONENT CAMERA FEED ---
const CameraFeed = ({
  src,
  label,
  location,
  status = "live",
}: {
  src: string;
  label: string;
  location: string;
  status?: "live" | "offline";
  useWebcam?: boolean;
}) => {
  const [error, setError] = useState(false);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:shadow-md transition-all group">
      <div className="p-3 bg-slate-50/50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="size-7 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
              <Video className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <span className="font-bold text-sm text-slate-800 dark:text-slate-100">
              {label}
            </span>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold shadow-sm ${status === "live"
              ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
              : "bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400"
              }`}
          >
            <span
              className={`size-1.5 rounded-full ${status === "live" ? "bg-emerald-500" : "bg-rose-500"
                }`}
            ></span>
            {status === "live" ? "TRỰC TUYẾN" : "MẤT TÍN HIỆU"}
          </span>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 ml-9 mt-0.5">
          {location}
        </p>
      </div>

      <div className="relative aspect-video bg-black flex items-center justify-center">
        {!error ? (
          <img
            src={src}
            alt={label}
            className="w-full h-full object-cover"
            onError={() => setError(true)}
            loading="lazy"
          />
        ) : (
          <div className="flex flex-col items-center text-slate-400 gap-2">
            <div className="size-12 rounded-full bg-slate-800 flex items-center justify-center">
              <VideoOff className="h-6 w-6 opacity-50" />
            </div>
            <span className="text-xs font-medium">
              Không thể kết nối camera
            </span>
          </div>
        )}

        {/* Overlay REC */}
        <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-black/60 px-2.5 py-1 rounded-lg text-[10px] text-white backdrop-blur-sm font-bold tracking-wider">
          <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse"></div>
          REC
        </div>

        {/* Timestamp overlay */}
        <div className="absolute bottom-2 left-2 bg-black/60 px-2.5 py-1 rounded-lg text-[10px] text-white/80 backdrop-blur-sm font-mono">
          {new Date().toLocaleTimeString("vi-VN", { hour12: false })}
        </div>
      </div>
    </div>
  );
};

// --- STATUS CARD COMPONENT (Redesigned) ---
const StatusCardNew = ({
  title,
  value,
  icon: Icon,
  description,
  alert = false,
  iconBg = "bg-primary/10",
  iconColor = "text-primary",
  valueSuffix,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  description: string;
  alert?: boolean;
  iconBg?: string;
  iconColor?: string;
  valueSuffix?: string;
}) => {
  return (
    <div
      className={`bg-white dark:bg-slate-900 rounded-xl border shadow-sm p-6 transition-all hover:shadow-md ${alert
        ? "border-rose-300 dark:border-rose-700 bg-rose-50/50 dark:bg-rose-950/20"
        : "border-slate-200 dark:border-slate-800"
        }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <span
            className={`text-xs font-bold uppercase tracking-widest ${alert
              ? "text-rose-600 dark:text-rose-400"
              : "text-slate-400 dark:text-slate-500"
              }`}
          >
            {title}
          </span>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span
              className={`text-2xl font-black tracking-tight ${alert
                ? "text-rose-600 dark:text-rose-400"
                : "text-slate-900 dark:text-white"
                }`}
            >
              {value}
            </span>
            {valueSuffix && (
              <span className="text-sm font-medium text-slate-400">
                {valueSuffix}
              </span>
            )}
          </div>
          <span
            className={`text-xs font-medium mt-1 ${alert
              ? "text-rose-500 dark:text-rose-400"
              : "text-slate-500 dark:text-slate-400"
              }`}
          >
            {description}
          </span>
        </div>
        <div
          className={`size-11 rounded-xl flex items-center justify-center shadow-sm ${alert ? "bg-rose-100 dark:bg-rose-900/30" : iconBg
            }`}
        >
          <Icon
            className={`w-5 h-5 ${alert ? "text-rose-600 dark:text-rose-400 animate-pulse" : iconColor
              }`}
          />
        </div>
      </div>
    </div>
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

// --- LOG INTERFACE ---
interface LogEntry {
  name: string;
  id: string;
  loc: string;
  status: string;
  time: string;
}

// --- MAIN DASHBOARD COMPONENT ---
export default function Dashboard() {
  const [chartData, setChartData] = useState(initialChartData);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [gpuLoad, setGpuLoad] = useState(0);
  const [temp, setTemp] = useState(40);
  const [presentCount, setPresentCount] = useState(0);
  const [totalEmployees, setTotalEmployees] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [searchLog, setSearchLog] = useState("");
  const [logFilter, setLogFilter] = useState("all");

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const res = await fetch("http://localhost:5000/api/dashboard-stats");
        const data = await res.json();

        setPresentCount(data.present_count);
        setTotalEmployees(data.total_employees);
        setWarningCount(data.warning_count);
        setLogs(data.logs);
        setGpuLoad(data.gpu_load);
        setTemp(data.temp);

        const now = new Date();
        const timeString = now.toLocaleTimeString("vi-VN", { hour12: false });

        setChartData((prevData) => {
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

    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 1000);
    return () => clearInterval(interval);
  }, []);

  // Filtered logs
  const filteredLogs = logs.filter((log) => {
    const matchSearch =
      !searchLog.trim() ||
      log.name.toLowerCase().includes(searchLog.toLowerCase()) ||
      log.id.toLowerCase().includes(searchLog.toLowerCase());
    const matchFilter =
      logFilter === "all" ||
      (logFilter === "warning" && log.status === "Cảnh báo") ||
      (logFilter === "normal" && log.status !== "Cảnh báo");
    return matchSearch && matchFilter;
  });

  return (
    <Layout>
      <div className="h-[calc(100vh-100px)] w-full overflow-y-auto custom-scrollbar font-sans bg-white dark:bg-[#101922]">
        <div className="p-8 space-y-8">
          <div className="w-full h-full animate-in fade-in duration-500">
            <div className="space-y-6">
              {/* Breadcrumbs */}
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 font-medium">
                <a
                  className="hover:text-primary transition-colors"
                  href="#"
                >
                  Trang chủ
                </a>
                <ChevronRight className="w-3.5 h-3.5" />
                <a
                  className="hover:text-primary transition-colors"
                  href="#"
                >
                  Giám sát
                </a>
                <ChevronRight className="w-3.5 h-3.5" />
                <span className="text-slate-900 dark:text-slate-100 font-medium">
                  Trung tâm giám sát AI
                </span>
              </div>

              {/* Title Block */}
              <div className="flex flex-wrap items-center justify-between gap-6 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4 w-full">
                  <div>
                    <h1 className="text-[#111418] dark:text-white text-3xl font-black tracking-tight mb-2">
                      Hệ Thống An Ninh AI - VHU
                    </h1>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 px-4 h-10 border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 rounded-lg text-sm font-bold">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                      </span>
                      SYSTEM ONLINE
                    </div>
                    <button className="flex items-center gap-2 px-4 h-10 border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-lg text-sm font-bold hover:bg-slate-50 transition-all">
                      <Download className="w-4 h-4" />
                      Xuất báo cáo
                    </button>
                  </div>
                </div>
              </div>

              {/* Global Search Bar (Kéo dài ra theo yêu cầu) */}
              <div className="relative w-full h-14 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center px-6 group focus-within:ring-2 focus-within:ring-primary/20 transition-all">
                <Search className="w-6 h-6 text-slate-400 group-focus-within:text-primary transition-colors shrink-0" />
                <input 
                  type="text" 
                  placeholder="Tìm kiếm nhanh trong hệ thống: Nhân sự, Sự kiện lạ, Luồng camera, Cấu hình AI..." 
                  className="flex-1 bg-transparent border-none outline-none px-4 text-slate-900 dark:text-slate-100 font-semibold placeholder:text-slate-400 text-lg"
                />
                <div className="hidden md:flex items-center gap-2 shrink-0">
                   <kbd className="text-[10px] font-black text-slate-400 bg-slate-50 dark:bg-slate-800 px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700">CTRL</kbd>
                   <kbd className="text-[10px] font-black text-slate-400 bg-slate-50 dark:bg-slate-800 px-2 py-1 rounded-md border border-slate-200 dark:border-slate-700">K</kbd>
                </div>
              </div>
            </div>

            {/* Summary Cards */}
            <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <StatusCardNew
                title="Sinh viên / Nhân sự"
                value={`${presentCount} `}
                valueSuffix={`/ ${totalEmployees} `}
                icon={Users}
                description={`Tỷ lệ: ${totalEmployees > 0
                  ? ((presentCount / totalEmployees) * 100).toFixed(1)
                  : 0
                  }% có mặt trên Campus`}
                iconBg="bg-indigo-100 dark:bg-indigo-900/30"
                iconColor="text-indigo-600 dark:text-indigo-400"
              />

              <StatusCardNew
                title={
                  warningCount > 0 ? "CẢNH BÁO GIẢ MẠO/LẠ" : "Trạng thái an ninh"
                }
                value={
                  warningCount > 0 ? `${warningCount} BÁO ĐỘNG` : "An toàn"
                }
                icon={warningCount > 0 ? AlertTriangle : CheckCircle}
                description={
                  warningCount > 0
                    ? "Có sự kiện khuôn mặt giả mạo/người lạ!"
                    : "Khu vực khuôn viên an tàn"
                }
                alert={warningCount > 0}
                iconBg="bg-emerald-100 dark:bg-emerald-900/30"
                iconColor="text-emerald-600 dark:text-emerald-400"
              />

              <StatusCardNew
                title="Kiểm soát truy cập"
                value="Hoạt động"
                icon={DoorClosed}
                description="Các chốt chặn Liveness / Giảng đường"
                iconBg="bg-amber-100 dark:bg-amber-900/30"
                iconColor="text-amber-600 dark:text-amber-400"
              />

              <StatusCardNew
                title="Hệ thống AI Server"
                value={`Tải GPU ${gpuLoad}% `}
                icon={Activity}
                description={`Nhiệt độ: ${temp}°C • Nhận diện thời gian thực`}
                iconBg="bg-purple-100 dark:bg-purple-900/30"
                iconColor="text-purple-600 dark:text-purple-400"
              />
            </div>

            {/* Camera Feeds - High Priority Focus */}
            <div className="mt-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
              <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
                <div className="flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                    <Eye className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                      Camera An Ninh
                    </h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Theo dõi cổng soát vẻ & khu vực hạn chế
                    </p>
                  </div>
                </div>

              </div>
              <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 bg-[#f4f7fa] dark:bg-[#0a1017]">
                <CameraFeed
                  src="http://localhost:5000/video_feed/0"
                  label="CAM-01: Sảnh A"
                  location="Sảnh Chính - Tầng 1"
                  status="live"
                />
                <CameraFeed
                  src="https://unizone.edu.vn/wp-content/uploads/2024/02/vhu-tru-so-chinh-613-au-co.jpg"
                  label="CAM-02: Khu vực cổng "
                  location="Ngoài trời - Tòa A"
                  status="live"
                />
              </div>
            </div>

            {/* Attendance Chart */}
            <div className="mt-6 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
              <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
                <div className="flex items-center gap-3">
                  <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <TrendingUp className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                      Lưu lượng phân tích AI
                    </h3>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Nhận diện sinh viên & xử lý chống giả mạo
                    </p>
                  </div>
                </div>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-[11px] font-bold animate-pulse">
                  <span className="size-1.5 rounded-full bg-emerald-500"></span>
                  LIVE UPDATING
                </span>
              </div>
              <div className="p-4">
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
                        tickFormatter={(value) => `${value} `}
                        domain={[0, 100]}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          borderColor: "hsl(var(--border))",
                          borderRadius: "12px",
                          color: "hsl(var(--foreground))",
                          boxShadow:
                            "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
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
              </div>
            </div>

            {/* Recent Logs Table */}
            <div className="mt-6 bg-white dark:bg-slate-900 rounded-xl border border-[#e7edf3] dark:border-slate-800 shadow-sm flex flex-col overflow-hidden">
              {/* Table Header */}
              <div className="p-6 border-b border-[#e7edf3] dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="size-8 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                      <Clock className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                        Nhật ký Nhận diện (Live Feed)
                      </h3>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        Lịch sử nhận diện Sinh viên, Cán bộ & phát hiện người lạ, giả mạo
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[11px] font-bold uppercase tracking-wider">
                      {filteredLogs.length} events
                    </span>
                    {warningCount > 0 && (
                      <span className="px-2.5 py-1 rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400 text-[11px] font-bold uppercase tracking-wider animate-pulse">
                        {warningCount} cảnh báo
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Alert Banner */}
              {warningCount > 0 && (
                <div className="mx-4 mt-4 p-4 rounded-xl border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/20 flex items-center gap-4 animate-pulse">
                  <div className="size-10 rounded-xl bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center flex-shrink-0">
                    <ShieldAlert className="h-5 w-5 text-rose-600 dark:text-rose-400" />
                  </div>
                  <div>
                    <p className="font-bold text-sm text-rose-700 dark:text-rose-400">
                      PHÁT HIỆN XÂM NHẬP!
                    </p>
                    <p className="text-xs text-rose-600 dark:text-rose-400/80 mt-0.5">
                      Hệ thống đang theo dõi{" "}
                      <span className="font-black text-base">
                        {warningCount}
                      </span>{" "}
                      đối tượng lạ mặt.
                    </p>
                  </div>
                </div>
              )}

              {/* Filter Bar for Logs */}
              <div className="p-6 flex flex-wrap items-center gap-3">
                {/* Search */}
                <div className="flex-1 min-w-[250px]">
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      className="w-full pl-9 pr-4 py-2 bg-slate-100 dark:bg-slate-800 border-none rounded-lg text-sm focus:ring-1 focus:ring-primary outline-none text-slate-700 dark:text-slate-300 placeholder:text-slate-400"
                      placeholder="Tìm kiếm theo tên, ID..."
                      type="text"
                      value={searchLog}
                      onChange={(e) => setSearchLog(e.target.value)}
                    />
                    {searchLog && (
                      <button
                        onClick={() => setSearchLog("")}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Log Status Filter */}
                <div className="relative">
                  <select
                    value={logFilter}
                    onChange={(e) => setLogFilter(e.target.value)}
                    className="appearance-none pl-4 pr-10 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors focus:outline-none cursor-pointer border-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="all">Tất cả trạng thái</option>
                    <option value="normal">Đã nhận diện</option>
                    <option value="warning">Cảnh báo</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              </div>

              {/* Logs Table */}
              <div className="flex-1 overflow-auto custom-scrollbar">
                <table className="w-full text-left border-collapse">
                  <thead className="sticky top-0 bg-white dark:bg-slate-900 z-10 shadow-sm">
                    <tr className="border-b border-slate-100 dark:border-slate-800">
                      <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">
                        Nhân sự
                      </th>
                      <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">
                        Mã NV
                      </th>
                      <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">
                        Vị trí
                      </th>
                      <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">
                        Trạng thái
                      </th>
                      <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">
                        Thời gian
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                    {filteredLogs.map((log, i) => (
                      <tr
                        key={i}
                        className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors group animate-in slide-in-from-left-2 duration-300"
                      >
                        <td className="p-4">
                          <div className="flex items-center gap-3">
                            <div
                              className={`size-9 rounded-lg flex items-center justify-center font-bold text-xs uppercase shadow-sm ${log.status === "Cảnh báo"
                                ? "bg-rose-100 text-rose-700"
                                : "bg-indigo-100 text-indigo-700"
                                }`}
                            >
                              {log.name
                                .split(" ")
                                .map((n) => n[0])
                                .slice(0, 2)
                                .join("")}
                            </div>
                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
                              {log.name}
                            </span>
                          </div>
                        </td>
                        <td className="p-4">
                          <span className="text-[11px] text-slate-400 font-medium italic">
                            {log.id}
                          </span>
                        </td>
                        <td className="p-4">
                          <span className="text-sm text-slate-600 dark:text-slate-400">
                            {log.loc}
                          </span>
                        </td>
                        <td className="p-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold shadow-sm ${log.status === "Cảnh báo"
                              ? "bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400"
                              : "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
                              }`}
                          >
                            <span
                              className={`size-1.5 rounded-full ${log.status === "Cảnh báo"
                                ? "bg-rose-500"
                                : "bg-emerald-500"
                                }`}
                            ></span>
                            {log.status}
                          </span>
                        </td>
                        <td className="p-4 text-xs text-slate-500 dark:text-slate-400 font-mono">
                          {log.time}
                        </td>
                      </tr>
                    ))}
                    {filteredLogs.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-16 text-center">
                          <div className="size-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4">
                            <Users className="w-8 h-8 text-slate-400" />
                          </div>
                          <p className="text-slate-700 dark:text-slate-300 font-bold text-lg">
                            Chưa có nhật ký nào
                          </p>
                          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                            Dữ liệu sẽ xuất hiện khi hệ thống nhận diện được
                            khuôn mặt
                          </p>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Table Footer */}
              <div className="p-4 border-t border-[#e7edf3] dark:border-slate-800 flex items-center justify-between bg-slate-50/30 dark:bg-slate-900/50 shrink-0">
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  Hiển thị{" "}
                  <span className="font-bold text-primary">
                    {filteredLogs.length}
                  </span>{" "}
                  bản ghi
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  Cập nhật mỗi 1 giây
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}