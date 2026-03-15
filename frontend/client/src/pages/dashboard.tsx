import React, { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  Download,
  TrendingUp,
  Eye,
  Clock,
  ChevronDown,
  X,
  Search,
  FileBarChart,
  Monitor,
  BarChart3,
  Shield,
  UserCheck,
  UserX,
  CalendarDays,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
} from "recharts";

// --- CAMERA FEED COMPONENT ---
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
              className={`size-1.5 rounded-full ${status === "live" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
                }`}
            ></span>
            {status === "live" ? "LIVE" : "OFFLINE"}
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
            <span className="text-xs font-medium">Không thể kết nối</span>
          </div>
        )}
        <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-black/60 px-2.5 py-1 rounded-lg text-[10px] text-white backdrop-blur-sm font-bold tracking-wider">
          <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse"></div>
          REC
        </div>
        <div className="absolute bottom-2 left-2 bg-black/60 px-2.5 py-1 rounded-lg text-[10px] text-white/80 backdrop-blur-sm font-mono">
          {new Date().toLocaleTimeString("vi-VN", { hour12: false })}
        </div>
      </div>
    </div>
  );
};

// --- STATUS CARD ---
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
            className={`w-5 h-5 ${alert
              ? "text-rose-600 dark:text-rose-400 animate-pulse"
              : iconColor
              }`}
          />
        </div>
      </div>
    </div>
  );
};

// --- REPORT STAT CARD ---
const ReportStatCard = ({
  title,
  value,
  change,
  changeType,
  icon: Icon,
  iconBg,
  iconColor,
}: {
  title: string;
  value: string;
  change: string;
  changeType: "up" | "down" | "neutral";
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
}) => (
  <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-5 hover:shadow-md transition-all">
    <div className="flex items-center justify-between">
      <div
        className={`size-10 rounded-xl flex items-center justify-center ${iconBg}`}
      >
        <Icon className={`w-5 h-5 ${iconColor}`} />
      </div>
      <div
        className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-full ${changeType === "up"
          ? "text-emerald-700 bg-emerald-100 dark:text-emerald-400 dark:bg-emerald-900/30"
          : changeType === "down"
            ? "text-rose-700 bg-rose-100 dark:text-rose-400 dark:bg-rose-900/30"
            : "text-slate-500 bg-slate-100 dark:text-slate-400 dark:bg-slate-800"
          }`}
      >
        {changeType === "up" ? (
          <ArrowUpRight className="w-3 h-3" />
        ) : changeType === "down" ? (
          <ArrowDownRight className="w-3 h-3" />
        ) : null}
        {change}
      </div>
    </div>
    <p className="text-2xl font-black text-slate-900 dark:text-white mt-3">
      {value}
    </p>
    <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mt-1">
      {title}
    </p>
  </div>
);

// --- DATA ---
const initialChartData = [
  { time: "10:00", visits: 45 },
  { time: "10:05", visits: 52 },
  { time: "10:10", visits: 38 },
  { time: "10:15", visits: 65 },
  { time: "10:20", visits: 48 },
  { time: "10:25", visits: 60 },
  { time: "10:30", visits: 55 },
];

const weeklyData = [
  { name: "T2", access: 420, alerts: 2, spoof: 1 },
  { name: "T3", access: 380, alerts: 5, spoof: 3 },
  { name: "T4", access: 500, alerts: 1, spoof: 0 },
  { name: "T5", access: 450, alerts: 3, spoof: 2 },
  { name: "T6", access: 480, alerts: 0, spoof: 0 },
  { name: "T7", access: 120, alerts: 8, spoof: 5 },
  { name: "CN", access: 90, alerts: 1, spoof: 0 },
];

const monthlyTrend = [
  { name: "Tuần 1", nhanVien: 380, nguoiLa: 12, giaMao: 3 },
  { name: "Tuần 2", nhanVien: 420, nguoiLa: 8, giaMao: 1 },
  { name: "Tuần 3", nhanVien: 450, nguoiLa: 15, giaMao: 5 },
  { name: "Tuần 4", nhanVien: 410, nguoiLa: 10, giaMao: 2 },
];

const pieData = [
  { name: "Nhân viên", value: 850 },
  { name: "Người lạ", value: 45 },
  { name: "Giả mạo", value: 12 },
  { name: "Khách", value: 120 },
];

const PIE_COLORS = ["#6366f1", "#f97316", "#ef4444", "#22c55e"];

const spoofMethodData = [
  { name: "Ảnh in", value: 45 },
  { name: "Điện thoại", value: 35 },
  { name: "Video", value: 15 },
  { name: "Khác", value: 5 },
];

const SPOOF_COLORS = ["#ef4444", "#f97316", "#eab308", "#94a3b8"];

interface LogEntry {
  name: string;
  id: string;
  loc: string;
  status: string;
  time: string;
}

// --- MAIN COMPONENT ---
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
    const fetchData = async () => {
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
        const ts = now.toLocaleTimeString("vi-VN", { hour12: false });
        setChartData((prev) => [
          ...prev.slice(1),
          { time: ts, visits: data.present_count },
        ]);
      } catch (err) {
        console.error("API Error:", err);
      }
    };
    fetchData();
    const iv = setInterval(fetchData, 1000);
    return () => clearInterval(iv);
  }, []);

  const filteredLogs = logs.filter((log) => {
    const ms =
      !searchLog.trim() ||
      log.name.toLowerCase().includes(searchLog.toLowerCase()) ||
      log.id.toLowerCase().includes(searchLog.toLowerCase());
    const mf =
      logFilter === "all" ||
      (logFilter === "warning" && log.status === "Cảnh báo") ||
      (logFilter === "normal" && log.status !== "Cảnh báo");
    return ms && mf;
  });

  return (
    <Layout>
      <div className="h-[calc(100vh-100px)] w-full overflow-y-auto custom-scrollbar font-sans bg-white dark:bg-[#101922]">
        <div className="p-8 space-y-6">
          {/* Breadcrumbs */}
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 font-medium">
            <a className="hover:text-primary transition-colors" href="#">
              Trang chủ
            </a>
            <ChevronRight className="w-3.5 h-3.5" />
            <a className="hover:text-primary transition-colors" href="#">
              Giám sát
            </a>
            <ChevronRight className="w-3.5 h-3.5" />
            <span className="text-slate-900 dark:text-slate-100 font-medium">
              Trung tâm giám sát AI
            </span>
          </div>

          {/* Title Block */}
          <div className="flex flex-wrap items-center justify-between gap-6 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <div>
              <h1 className="text-[#111418] dark:text-white text-3xl font-black tracking-tight mb-1">
                Hệ Thống An Ninh AI - VHU
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Giám sát camera, nhận diện khuôn mặt & chống giả mạo thời gian thực
              </p>
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

          {/* ════════════════════════════════════════════════════ */}
          {/* ★★★ TABS: GIÁM SÁT | BÁO CÁO & THỐNG KÊ          */}
          {/* ════════════════════════════════════════════════════ */}
          <Tabs defaultValue="surveillance" className="w-full">
            <TabsList className="w-full max-w-lg mx-auto grid grid-cols-2 h-12 bg-slate-100 dark:bg-slate-800 rounded-xl p-1">
              <TabsTrigger
                value="surveillance"
                className="flex items-center gap-2 rounded-lg text-sm font-bold data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:shadow-sm transition-all"
              >
                <Monitor className="w-4 h-4" />
                Giám sát trực tiếp
              </TabsTrigger>
              <TabsTrigger
                value="reports"
                className="flex items-center gap-2 rounded-lg text-sm font-bold data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:shadow-sm transition-all"
              >
                <BarChart3 className="w-4 h-4" />
                Báo cáo & Thống kê
              </TabsTrigger>
            </TabsList>

            {/* ══════════════════════════════════════════════════ */}
            {/* TAB 1: GIÁM SÁT TRỰC TIẾP                        */}
            {/* ══════════════════════════════════════════════════ */}
            <TabsContent value="surveillance" className="mt-6 space-y-6">
              {/* Summary Cards */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatusCardNew
                  title="Sinh viên / Nhân sự"
                  value={`${presentCount}`}
                  valueSuffix={`/ ${totalEmployees}`}
                  icon={Users}
                  description={`Tỷ lệ: ${totalEmployees > 0
                    ? ((presentCount / totalEmployees) * 100).toFixed(1)
                    : 0
                    }% có mặt`}
                  iconBg="bg-indigo-100 dark:bg-indigo-900/30"
                  iconColor="text-indigo-600 dark:text-indigo-400"
                />
                <StatusCardNew
                  title={warningCount > 0 ? "CẢNH BÁO AN NINH" : "Trạng thái an ninh"}
                  value={warningCount > 0 ? `${warningCount} BÁO ĐỘNG` : "An toàn"}
                  icon={warningCount > 0 ? AlertTriangle : CheckCircle}
                  description={
                    warningCount > 0
                      ? "Phát hiện giả mạo/người lạ!"
                      : "Khuôn viên an toàn"
                  }
                  alert={warningCount > 0}
                  iconBg="bg-emerald-100 dark:bg-emerald-900/30"
                  iconColor="text-emerald-600 dark:text-emerald-400"
                />
                <StatusCardNew
                  title="Kiểm soát truy cập"
                  value="Hoạt động"
                  icon={DoorClosed}
                  description="Chốt Liveness / Giảng đường"
                  iconBg="bg-amber-100 dark:bg-amber-900/30"
                  iconColor="text-amber-600 dark:text-amber-400"
                />
                <StatusCardNew
                  title="AI Server"
                  value={`GPU ${gpuLoad}%`}
                  icon={Activity}
                  description={`${temp}°C • Real-time`}
                  iconBg="bg-purple-100 dark:bg-purple-900/30"
                  iconColor="text-purple-600 dark:text-purple-400"
                />
              </div>

              {/* 6 Camera Feeds */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                        <Eye className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          Hệ thống Camera An Ninh
                        </h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          6 camera giám sát toàn bộ khuôn viên
                        </p>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-[11px] font-bold">
                      <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      6/6 ONLINE
                    </span>
                  </div>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 bg-[#f4f7fa] dark:bg-[#0a1017]">
                  <CameraFeed
                    src="http://localhost:5000/video_feed/0"
                    label="CAM-01: Sảnh chính"
                    location="Sảnh A - Tầng 1"
                    status="live"
                  />
                  <CameraFeed
                    src="https://unizone.edu.vn/wp-content/uploads/2024/02/vhu-tru-so-chinh-613-au-co.jpg"
                    label="CAM-02: Cổng chính"
                    location="Cổng ra vào - Ngoài trời"
                    status="live"
                  />
                  <CameraFeed
                    src="https://images.unsplash.com/photo-1562774053-701939374585?w=640&h=360&fit=crop"
                    label="CAM-03: Hành lang B"
                    location="Tòa B - Tầng 2"
                    status="live"
                  />
                  <CameraFeed
                    src="https://images.unsplash.com/photo-1541829070764-84a7d30dd3f3?w=640&h=360&fit=crop"
                    label="CAM-04: Hội Trường"
                    location="Bãi xe A - Ngoài trời"
                    status="live"
                  />
                  <CameraFeed
                    src="https://images.unsplash.com/photo-1580582932707-520aed937b7b?w=640&h=360&fit=crop"
                    label="CAM-05: Thư viện"
                    location="Thư viện - Tầng 1"
                    status="live"
                  />
                  <CameraFeed
                    src="https://images.unsplash.com/photo-1497366216548-37526070297c?w=640&h=360&fit=crop"
                    label="CAM-06: Phòng server"
                    location="Tầng hầm - Khu vực hạn chế"
                    status="live"
                  />
                </div>
              </div>

              {/* Live Chart */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
                  <div className="flex items-center gap-3">
                    <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <TrendingUp className="w-4 h-4 text-primary" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                        Lưu lượng AI phân tích
                      </h3>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        Nhận diện & chống giả mạo real-time
                      </p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-[11px] font-bold animate-pulse">
                    <span className="size-1.5 rounded-full bg-emerald-500"></span>
                    LIVE
                  </span>
                </div>
                <div className="p-4">
                  <div className="h-[280px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id="colorVisits" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                        <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                        <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} domain={[0, 100]} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "hsl(var(--card))",
                            borderColor: "hsl(var(--border))",
                            borderRadius: "10px",
                            color: "hsl(var(--foreground))",
                          }}
                        />
                        <Area type="monotone" dataKey="visits" stroke="hsl(var(--primary))" strokeWidth={2} fillOpacity={1} fill="url(#colorVisits)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Logs Table */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col overflow-hidden">
                <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                        <Clock className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          Nhật ký nhận diện
                        </h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Lịch sử nhận diện & phát hiện bất thường
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[11px] font-bold">
                        {filteredLogs.length} events
                      </span>
                      {warningCount > 0 && (
                        <span className="px-2.5 py-1 rounded-full bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400 text-[11px] font-bold animate-pulse">
                          {warningCount} cảnh báo
                        </span>
                      )}
                    </div>
                  </div>
                </div>

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
                        Đang theo dõi{" "}
                        <span className="font-black text-base">{warningCount}</span>{" "}
                        đối tượng.
                      </p>
                    </div>
                  </div>
                )}

                <div className="p-6 flex flex-wrap items-center gap-3">
                  <div className="flex-1 min-w-[250px]">
                    <div className="relative">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        className="w-full pl-9 pr-4 py-2 bg-slate-100 dark:bg-slate-800 border-none rounded-lg text-sm focus:ring-1 focus:ring-primary outline-none text-slate-700 dark:text-slate-300 placeholder:text-slate-400"
                        placeholder="Tìm theo tên, ID..."
                        value={searchLog}
                        onChange={(e) => setSearchLog(e.target.value)}
                      />
                      {searchLog && (
                        <button onClick={() => setSearchLog("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="relative">
                    <select
                      value={logFilter}
                      onChange={(e) => setLogFilter(e.target.value)}
                      className="appearance-none pl-4 pr-10 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-medium border-none focus:ring-1 focus:ring-primary cursor-pointer"
                    >
                      <option value="all">Tất cả</option>
                      <option value="normal">Đã nhận diện</option>
                      <option value="warning">Cảnh báo</option>
                    </select>
                    <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>

                <div className="flex-1 overflow-auto custom-scrollbar">
                  <table className="w-full text-left border-collapse">
                    <thead className="sticky top-0 bg-white dark:bg-slate-900 z-10 shadow-sm">
                      <tr className="border-b border-slate-100 dark:border-slate-800">
                        <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">Nhân sự</th>
                        <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">Phòng ban</th>
                        <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">Vị trí</th>
                        <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">Trạng thái</th>
                        <th className="p-4 text-xs font-bold text-slate-400 uppercase tracking-widest">Thời gian</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                      {filteredLogs.map((log, i) => (
                        <tr key={i} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                          <td className="p-4">
                            <div className="flex items-center gap-3">
                              <div className={`size-9 rounded-lg flex items-center justify-center font-bold text-xs uppercase shadow-sm ${log.status === "Cảnh báo" ? "bg-rose-100 text-rose-700" : "bg-indigo-100 text-indigo-700"}`}>
                                {log.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                              </div>
                              <span className="text-sm font-bold text-slate-800 dark:text-slate-100">{log.name}</span>
                            </div>
                          </td>
                          <td className="p-4 text-[11px] text-slate-400 font-medium">{log.id}</td>
                          <td className="p-4 text-sm text-slate-600 dark:text-slate-400">{log.loc}</td>
                          <td className="p-4">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold shadow-sm ${log.status === "Cảnh báo" ? "bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400" : "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"}`}>
                              <span className={`size-1.5 rounded-full ${log.status === "Cảnh báo" ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                              {log.status}
                            </span>
                          </td>
                          <td className="p-4 text-xs text-slate-500 dark:text-slate-400 font-mono">{log.time}</td>
                        </tr>
                      ))}
                      {filteredLogs.length === 0 && (
                        <tr>
                          <td colSpan={5} className="p-16 text-center">
                            <div className="size-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4">
                              <Users className="w-8 h-8 text-slate-400" />
                            </div>
                            <p className="text-slate-700 dark:text-slate-300 font-bold text-lg">Chưa có nhật ký</p>
                            <p className="text-sm text-slate-500 mt-1">Dữ liệu sẽ xuất hiện khi hệ thống nhận diện khuôn mặt</p>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/30 dark:bg-slate-900/50">
                  <span className="text-sm text-slate-500">
                    Hiển thị <span className="font-bold text-primary">{filteredLogs.length}</span> bản ghi
                  </span>
                  <span className="text-xs text-slate-400 font-mono">Cập nhật mỗi 1 giây</span>
                </div>
              </div>
            </TabsContent>

            {/* ══════════════════════════════════════════════════ */}
            {/* TAB 2: BÁO CÁO & THỐNG KÊ                       */}
            {/* ══════════════════════════════════════════════════ */}
            <TabsContent value="reports" className="mt-6 space-y-6">
              {/* Report Header */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="size-10 rounded-xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center shadow-sm">
                    <FileBarChart className="w-5 h-5 text-violet-600 dark:text-violet-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-black text-slate-900 dark:text-white tracking-tight">
                      Báo cáo & Thống kê hệ thống
                    </h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      Trực quan hóa dữ liệu, phân tích xu hướng & hiệu suất AI
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 px-3 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
                    <CalendarDays className="w-4 h-4 text-slate-500" />
                    <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                      {new Date().toLocaleDateString("vi-VN", {
                        weekday: "long",
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  <button className="flex items-center gap-2 px-4 h-10 border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-lg text-sm font-bold hover:bg-slate-50 dark:hover:bg-slate-700 transition-all shadow-sm">
                    <Download className="w-4 h-4" />
                    Tải PDF
                  </button>
                </div>
              </div>

              {/* Report Summary Cards */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <ReportStatCard
                  title="Tổng lượt nhận diện tuần"
                  value="2,440"
                  change="+12.5%"
                  changeType="up"
                  icon={UserCheck}
                  iconBg="bg-indigo-100 dark:bg-indigo-900/30"
                  iconColor="text-indigo-600 dark:text-indigo-400"
                />
                <ReportStatCard
                  title="Người lạ phát hiện"
                  value="45"
                  change="-8.2%"
                  changeType="down"
                  icon={UserX}
                  iconBg="bg-amber-100 dark:bg-amber-900/30"
                  iconColor="text-amber-600 dark:text-amber-400"
                />
                <ReportStatCard
                  title="Giả mạo bị chặn"
                  value="12"
                  change="+2"
                  changeType="up"
                  icon={Shield}
                  iconBg="bg-rose-100 dark:bg-rose-900/30"
                  iconColor="text-rose-600 dark:text-rose-400"
                />
                <ReportStatCard
                  title="Độ chính xác AI"
                  value="98.7%"
                  change="+0.3%"
                  changeType="up"
                  icon={Activity}
                  iconBg="bg-emerald-100 dark:bg-emerald-900/30"
                  iconColor="text-emerald-600 dark:text-emerald-400"
                />
              </div>

              {/* Charts Row 1: Bar + Pie */}
              <div className="grid gap-6 lg:grid-cols-7">
                {/* Weekly Bar Chart */}
                <div className="col-span-full lg:col-span-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                        <BarChart3 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          Lưu lượng truy cập hàng tuần
                        </h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Truy cập hợp lệ vs Cảnh báo vs Giả mạo
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="p-6">
                    <div className="h-[350px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={weeklyData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                          <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                          <Tooltip
                            cursor={{ fill: "hsl(var(--muted)/0.2)" }}
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              borderColor: "hsl(var(--border))",
                              borderRadius: "8px",
                              color: "hsl(var(--foreground))",
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: "12px", fontWeight: 600 }} />
                          <Bar dataKey="access" name="Truy cập hợp lệ" fill="#6366f1" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="alerts" name="Cảnh báo" fill="#f97316" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="spoof" name="Giả mạo" fill="#ef4444" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                {/* Access Distribution Pie */}
                <div className="col-span-full lg:col-span-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                        <Users className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          Phân phối đối tượng
                        </h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Phân loại theo kết quả nhận diện
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="p-6">
                    <div className="h-[260px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={90} paddingAngle={4} dataKey="value">
                            {pieData.map((_, index) => (
                              <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} stroke="transparent" />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              borderColor: "hsl(var(--border))",
                              borderRadius: "8px",
                              color: "hsl(var(--foreground))",
                            }}
                          />
                          <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: "11px", fontWeight: 600 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    {/* Stats grid */}
                    <div className="mt-3 grid grid-cols-4 gap-2">
                      {pieData.map((item, index) => (
                        <div key={index} className="text-center p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                          <div className="w-2.5 h-2.5 rounded-full mx-auto mb-1" style={{ backgroundColor: PIE_COLORS[index] }}></div>
                          <p className="text-base font-black text-slate-900 dark:text-white">{item.value}</p>
                          <p className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">{item.name}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Charts Row 2: Monthly Trend + Spoof Methods */}
              <div className="grid gap-6 lg:grid-cols-7">
                {/* Monthly Trend Line */}
                <div className="col-span-full lg:col-span-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                        <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          Xu hướng tháng
                        </h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Nhân viên vs Người lạ vs Giả mạo theo tuần
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="p-6">
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={monthlyTrend}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                          <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              borderColor: "hsl(var(--border))",
                              borderRadius: "8px",
                              color: "hsl(var(--foreground))",
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: "11px", fontWeight: 600 }} />
                          <Line type="monotone" dataKey="nhanVien" name="Nhân viên" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 4 }} />
                          <Line type="monotone" dataKey="nguoiLa" name="Người lạ" stroke="#f97316" strokeWidth={2.5} dot={{ r: 4 }} />
                          <Line type="monotone" dataKey="giaMao" name="Giả mạo" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 4 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                {/* Spoof Methods Pie */}
                <div className="col-span-full lg:col-span-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-3">
                      <div className="size-8 rounded-lg bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center">
                        <Shield className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                          Phương thức giả mạo
                        </h3>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Phân loại các hình thức tấn công bị phát hiện
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="p-6">
                    <div className="h-[220px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={spoofMethodData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                            {spoofMethodData.map((_, index) => (
                              <Cell key={index} fill={SPOOF_COLORS[index % SPOOF_COLORS.length]} stroke="transparent" />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "hsl(var(--card))",
                              borderColor: "hsl(var(--border))",
                              borderRadius: "8px",
                              color: "hsl(var(--foreground))",
                            }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    {/* Spoof stats list */}
                    <div className="mt-4 space-y-2">
                      {spoofMethodData.map((item, index) => (
                        <div key={index} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                          <div className="flex items-center gap-2.5">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: SPOOF_COLORS[index] }}></div>
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{item.name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-black text-slate-900 dark:text-white">{item.value}%</span>
                            <div className="w-16 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                              <div className="h-full rounded-full" style={{ width: `${item.value}%`, backgroundColor: SPOOF_COLORS[index] }}></div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* System Performance Summary */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50">
                  <div className="flex items-center gap-3">
                    <div className="size-8 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                      <Activity className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                        Hiệu suất hệ thống AI
                      </h3>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        Tổng quan năng lực xử lý & độ chính xác
                      </p>
                    </div>
                  </div>
                </div>
                <div className="p-6">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                    {/* Metric 1 */}
                    <div className="text-center">
                      <div className="relative size-24 mx-auto">
                        <svg className="size-24 -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" className="text-slate-100 dark:text-slate-800" />
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" strokeDasharray={`${98.7 * 2.64} ${264}`} strokeLinecap="round" className="text-emerald-500" />
                        </svg>
                        <span className="absolute inset-0 flex items-center justify-center text-lg font-black text-slate-900 dark:text-white">
                          98.7%
                        </span>
                      </div>
                      <p className="text-xs font-bold text-slate-500 mt-2">Độ chính xác</p>
                    </div>
                    {/* Metric 2 */}
                    <div className="text-center">
                      <div className="relative size-24 mx-auto">
                        <svg className="size-24 -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" className="text-slate-100 dark:text-slate-800" />
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" strokeDasharray={`${30 * 2.64} ${264}`} strokeLinecap="round" className="text-indigo-500" />
                        </svg>
                        <span className="absolute inset-0 flex items-center justify-center text-lg font-black text-slate-900 dark:text-white">
                          30fps
                        </span>
                      </div>
                      <p className="text-xs font-bold text-slate-500 mt-2">Tốc độ xử lý</p>
                    </div>
                    {/* Metric 3 */}
                    <div className="text-center">
                      <div className="relative size-24 mx-auto">
                        <svg className="size-24 -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" className="text-slate-100 dark:text-slate-800" />
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" strokeDasharray={`${gpuLoad * 2.64} ${264}`} strokeLinecap="round" className="text-amber-500" />
                        </svg>
                        <span className="absolute inset-0 flex items-center justify-center text-lg font-black text-slate-900 dark:text-white">
                          {gpuLoad}%
                        </span>
                      </div>
                      <p className="text-xs font-bold text-slate-500 mt-2">Tải GPU</p>
                    </div>
                    {/* Metric 4 */}
                    <div className="text-center">
                      <div className="relative size-24 mx-auto">
                        <svg className="size-24 -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" className="text-slate-100 dark:text-slate-800" />
                          <circle cx="50" cy="50" r="42" stroke="currentColor" strokeWidth="8" fill="none" strokeDasharray={`${(temp / 100) * 264} ${264}`} strokeLinecap="round" className="text-purple-500" />
                        </svg>
                        <span className="absolute inset-0 flex items-center justify-center text-lg font-black text-slate-900 dark:text-white">
                          {temp}°C
                        </span>
                      </div>
                      <p className="text-xs font-bold text-slate-500 mt-2">Nhiệt độ</p>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Layout>
  );
}