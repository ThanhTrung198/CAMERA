import React, { useState, useEffect, useCallback } from "react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ShieldAlert,
  UserX,
  Search,
  AlertTriangle,
  Clock,
  Camera,
  RefreshCw,
  Eye,
  ImageIcon,
  Video,
  Play,
  Download,
  Trash2,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Calendar,
  AlertOctagon,
  X,
  Shield,
  Film,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const API = "http://localhost:5000";

// ============================================================================
// TYPES
// ============================================================================
interface AlertItem {
  id: number;
  location: string;
  cam: string;
  date: string;
  time: string;
  img: string;
  count: number;
  details: { time: string; img: string }[];
  status?: string;
}

interface BlacklistItem {
  id: number;
  name: string;
  reason: string;
  date: string;
  img: string;
  status: string;
  count: number;
  details: { time: string; img: string; reason: string }[];
}

interface Snapshot {
  filename: string;
  url: string;
  time: string;
  person_id: string | null;
}

interface IntrusionEvent {
  id: number;
  video_filename: string;
  video_url: string;
  cam_id: string;
  timestamp: string;
  date: string;
  time: string;
  duration_s: number;
  size_mb: number;
  alert_level: string;
  snapshots: Snapshot[];
  snapshot_count: number;
  thumbnail: string | null;
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export default function Security() {
  // State - Tab 1
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [blacklist, setBlacklist] = useState<BlacklistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchBL, setSearchBL] = useState("");
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  // State - Tab 2
  const [events, setEvents] = useState<IntrusionEvent[]>([]);
  const [eventsPage, setEventsPage] = useState(1);
  const [eventsTotalPages, setEventsTotalPages] = useState(0);
  const [eventsTotal, setEventsTotal] = useState(0);
  const [dateFilter, setDateFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<IntrusionEvent | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);

  // ============================================================================
  // API CALLS
  // ============================================================================
  const getImageUrl = (path: string) => {
    if (!path || path === "") return "https://placehold.co/600x400?text=No+Image";
    if (path.startsWith("http")) return path;
    let cleanPath = path.replace(/\\/g, "/");
    if (!cleanPath.startsWith("/")) cleanPath = "/" + cleanPath;
    return `${API}${cleanPath}`;
  };

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/security/alerts`);
      const data = await res.json();
      setAlerts(data);
    } catch (e) { console.error("Fetch alerts error:", e); }
    finally { setLoading(false); }
  }, []);

  const fetchBlacklist = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/security/blacklist`);
      const data = await res.json();
      setBlacklist(data);
    } catch (e) { console.error("Fetch blacklist error:", e); }
  }, []);

  const fetchIntrusionEvents = useCallback(async (page = 1, date = "") => {
    try {
      setEventsLoading(true);
      let url = `${API}/api/security/intrusion-events?page=${page}&per_page=9`;
      if (date) url += `&date=${date}`;
      const res = await fetch(url);
      const data = await res.json();
      setEvents(data.events || []);
      setEventsPage(data.page || 1);
      setEventsTotalPages(data.total_pages || 0);
      setEventsTotal(data.total || 0);
    } catch (e) { console.error("Fetch events error:", e); }
    finally { setEventsLoading(false); }
  }, []);

  const handleAddToBlacklist = async (item: AlertItem) => {
    try {
      const res = await fetch(`${API}/api/security/blacklist/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `Đối tượng ${item.location}`,
          reason: `Phát hiện tại ${item.cam} lúc ${item.time}`,
          image: item.img,
        }),
      });
      const result = await res.json();
      if (result.success) { fetchBlacklist(); fetchAlerts(); }
    } catch (e) { console.error("Add blacklist error:", e); }
  };

  const handleDeleteBlacklist = async (id: number) => {
    if (!confirm("Bạn chắc chắn muốn xóa khỏi danh sách đen?")) return;
    try {
      const res = await fetch(`${API}/api/security/blacklist/${id}`, { method: "DELETE" });
      const result = await res.json();
      if (result.success) fetchBlacklist();
    } catch (e) { console.error("Delete blacklist error:", e); }
  };

  const handleVerifyAlert = async (id: number) => {
    try {
      const res = await fetch(`${API}/api/security/alerts/${id}/verify`, { method: "PUT" });
      const result = await res.json();
      if (result.success) fetchAlerts();
    } catch (e) { console.error("Verify alert error:", e); }
  };

  useEffect(() => {
    fetchAlerts();
    fetchBlacklist();
    fetchIntrusionEvents(1, "");
    const interval = setInterval(() => { fetchAlerts(); fetchBlacklist(); }, 8000);
    return () => clearInterval(interval);
  }, [fetchAlerts, fetchBlacklist, fetchIntrusionEvents]);

  // ============================================================================
  // SUB-COMPONENTS
  // ============================================================================

  // --- Alert Level Badge ---
  const AlertBadge = ({ level }: { level: string }) => {
    const colors: Record<string, string> = {
      critical: "bg-red-600 text-white animate-pulse",
      high: "bg-orange-500 text-white",
      medium: "bg-amber-500 text-white",
      low: "bg-blue-500 text-white",
    };
    const labels: Record<string, string> = {
      critical: "KHẨN CẤP", high: "CAO", medium: "TRUNG BÌNH", low: "THẤP"
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide ${colors[level] || colors.medium}`}>
        {labels[level] || level}
      </span>
    );
  };

  // --- Unknown Person Card ---
  const UnknownCard = ({ item }: { item: AlertItem }) => {
    const isVerified = item.location === "Đã xác minh";
    return (
      <Card className={`overflow-hidden border-l-4 transition-all hover:shadow-xl group
        ${isVerified ? "border-l-green-500 bg-green-50/30 dark:bg-green-950/10" : "border-l-amber-500 hover:border-l-amber-400"}`}
      >
        <div className="aspect-video w-full bg-muted relative cursor-pointer overflow-hidden"
          onClick={() => setSelectedAlert(item)}>
          <img src={getImageUrl(item.img)} alt="Detection"
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            onError={(e: any) => { e.target.src = "https://placehold.co/600x400?text=No+Image"; }} />

          <div className="absolute top-2 right-2 bg-black/70 backdrop-blur-sm text-white text-[11px] px-2 py-1 rounded-md font-mono flex items-center gap-1">
            <Camera className="h-3 w-3" /> {item.cam}
          </div>

          {item.count > 1 && (
            <div className="absolute top-2 left-2 bg-red-600 text-white text-[11px] px-2 py-1 rounded-full font-bold flex items-center gap-1 animate-pulse">
              <Eye className="h-3 w-3" /> {item.count}x
            </div>
          )}

          <div className={`absolute bottom-0 left-0 right-0 px-3 py-2 
            ${isVerified ? "bg-gradient-to-t from-green-900/80" : "bg-gradient-to-t from-black/80"}`}>
            <span className={`text-[11px] font-bold flex items-center gap-1 
              ${isVerified ? "text-green-300" : "text-amber-300"}`}>
              {isVerified ? <><CheckCircle className="h-3 w-3" /> ĐÃ XÁC MINH</> :
                <><AlertTriangle className="h-3 w-3" /> CHƯA XÁC MINH</>}
            </span>
          </div>
        </div>

        <CardContent className="p-3 space-y-2">
          <div className="flex justify-between items-start">
            <div className="space-y-0.5">
              <div className="font-semibold text-sm">{item.location || "Người lạ"}</div>
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" /> {item.date} • {item.time}
              </div>
            </div>
          </div>

          {!isVerified && (
            <div className="flex gap-1.5">
              <Button size="sm" variant="outline" className="flex-1 h-8 text-xs hover:bg-green-50 hover:text-green-700 hover:border-green-300"
                onClick={(e) => { e.stopPropagation(); handleVerifyAlert(item.id); }}>
                <CheckCircle className="mr-1 h-3 w-3" /> Xác minh
              </Button>
              <Button size="sm" className="flex-1 h-8 text-xs bg-red-600 hover:bg-red-700 text-white"
                onClick={(e) => { e.stopPropagation(); handleAddToBlacklist(item); }}>
                <UserX className="mr-1 h-3 w-3" /> Blacklist
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  // --- Blacklist Card ---
  const BlacklistCard = ({ item }: { item: BlacklistItem }) => (
    <Card className="overflow-hidden border-l-4 border-l-red-600 bg-red-50/30 dark:bg-red-950/10 transition-all hover:shadow-xl group">
      <div className="aspect-video w-full bg-muted relative overflow-hidden">
        <img src={getImageUrl(item.img)} alt="Blacklisted"
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          onError={(e: any) => { e.target.src = "https://placehold.co/600x400?text=No+Image"; }} />
        <div className="absolute top-2 left-2 bg-red-600/90 backdrop-blur-sm text-white text-[11px] px-2 py-1 rounded-md font-bold flex items-center gap-1 animate-pulse">
          <AlertOctagon className="h-3 w-3" /> ĐỐI TƯỢNG NGUY HIỂM
        </div>
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-red-900/80 px-3 py-2">
          <span className="text-white text-xs font-mono">ID: BL-{item.id}</span>
        </div>
      </div>
      <CardContent className="p-3 space-y-2">
        <div>
          <div className="font-bold text-sm text-red-700 dark:text-red-400">{item.name}</div>
          <div className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
            <Clock className="h-3 w-3" /> {item.date}
          </div>
          <div className="text-xs text-red-500/80 italic mt-0.5 truncate">Lý do: {item.reason}</div>
        </div>
        <Button size="sm" variant="outline" className="w-full h-8 text-xs border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
          onClick={() => handleDeleteBlacklist(item.id)}>
          <Trash2 className="mr-1 h-3 w-3" /> Xóa khỏi danh sách đen
        </Button>
      </CardContent>
    </Card>
  );

  // --- Intrusion Event Card ---
  const EventCard = ({ event }: { event: IntrusionEvent }) => (
    <Card className={`overflow-hidden cursor-pointer transition-all hover:shadow-xl hover:ring-2 group
      ${event.alert_level === "high" ? "hover:ring-orange-400 border-l-4 border-l-orange-500" :
        event.alert_level === "critical" ? "hover:ring-red-500 border-l-4 border-l-red-600 animate-pulse" :
          "hover:ring-blue-400 border-l-4 border-l-blue-500"}`}
      onClick={() => setSelectedEvent(event)}>

      <div className="aspect-video w-full bg-black/90 relative overflow-hidden">
        {event.thumbnail ? (
          <img src={event.thumbnail} alt="Intrusion"
            className="w-full h-full object-cover opacity-90 transition-transform duration-300 group-hover:scale-105"
            onError={(e: any) => { e.target.src = ""; e.target.style.display = "none"; }} />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Film className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}

        {/* Overlay badges */}
        <div className="absolute top-2 left-2">
          <AlertBadge level={event.alert_level} />
        </div>
        <div className="absolute top-2 right-2 bg-black/70 backdrop-blur-sm text-white text-[11px] px-2 py-1 rounded-md font-mono">
          {event.cam_id.toUpperCase()}
        </div>

        {/* Play icon on hover */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center">
          <div className="bg-white/90 rounded-full p-3 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
            <Play className="h-6 w-6 text-black fill-black" />
          </div>
        </div>

        {/* Bottom gradient */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 px-3 py-2">
          <div className="flex items-center justify-between text-white">
            <span className="text-[11px] font-mono">{event.size_mb} MB</span>
            <span className="text-[11px] flex items-center gap-1">
              <ImageIcon className="h-3 w-3" /> {event.snapshot_count} ảnh
            </span>
          </div>
        </div>
      </div>

      <CardContent className="p-3 space-y-1">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-sm">{event.video_filename.replace(/_/g, " ").replace(".mp4", "")}</span>
        </div>
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {event.date}</span>
          <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {event.time}</span>
        </div>
      </CardContent>
    </Card>
  );

  // --- Pagination ---
  const Pagination = ({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (p: number) => void }) => {
    if (totalPages <= 1) return null;
    return (
      <div className="flex items-center justify-center gap-2 mt-6">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="text-sm text-muted-foreground font-mono">
          {page} / {totalPages}
        </span>
        <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    );
  };

  // ============================================================================
  // RENDER
  // ============================================================================
  return (
    <Layout>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Shield className="h-8 w-8 text-red-500" />
              An ninh & Cảnh báo
            </h2>
            <p className="text-muted-foreground mt-1">
              Quản lý mối đe dọa, blacklist và bằng chứng xâm nhập
            </p>
          </div>
          <Button variant="outline" size="sm"
            onClick={() => { fetchAlerts(); fetchBlacklist(); fetchIntrusionEvents(eventsPage, dateFilter); }}
            disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
          </Button>
        </div>

        {/* Stats Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="border-amber-200/50 bg-amber-50/30 dark:bg-amber-950/10">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
              </div>
              <div>
                <div className="text-2xl font-bold">{alerts.length}</div>
                <div className="text-xs text-muted-foreground">Người lạ</div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-red-200/50 bg-red-50/30 dark:bg-red-950/10">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                <UserX className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <div className="text-2xl font-bold">{blacklist.length}</div>
                <div className="text-xs text-muted-foreground">Blacklist</div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-orange-200/50 bg-orange-50/30 dark:bg-orange-950/10">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
                <Video className="h-5 w-5 text-orange-500" />
              </div>
              <div>
                <div className="text-2xl font-bold">{eventsTotal}</div>
                <div className="text-xs text-muted-foreground">Video xâm nhập</div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-blue-200/50 bg-blue-50/30 dark:bg-blue-950/10">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Eye className="h-5 w-5 text-blue-500" />
              </div>
              <div>
                <div className="text-2xl font-bold">
                  {alerts.reduce((sum, a) => sum + a.count, 0)}
                </div>
                <div className="text-xs text-muted-foreground">Lượt phát hiện</div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="recognition" className="w-full">
          <TabsList className="grid w-full max-w-lg grid-cols-2 h-11">
            <TabsTrigger value="recognition" className="gap-2 text-sm">
              <ShieldAlert className="h-4 w-4" />
              Nhận diện & Blacklist
            </TabsTrigger>
            <TabsTrigger value="evidence" className="gap-2 text-sm">
              <Film className="h-4 w-4" />
              Bằng chứng xâm nhập
            </TabsTrigger>
          </TabsList>

          {/* ============================================================ */}
          {/* TAB 1: RECOGNITION & BLACKLIST                                */}
          {/* ============================================================ */}
          <TabsContent value="recognition" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
              {/* Người lạ - 3 cols */}
              <div className="lg:col-span-3 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-lg flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                    Người lạ phát hiện
                    <Badge variant="outline" className="ml-1">{alerts.length}</Badge>
                  </h3>
                </div>
                {alerts.length === 0 ? (
                  <Card className="border-dashed">
                    <CardContent className="py-12 flex flex-col items-center text-muted-foreground">
                      <Eye className="h-10 w-10 mb-3 opacity-30" />
                      <p>Chưa phát hiện người lạ nào</p>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {alerts.map((item) => (
                      <UnknownCard key={item.id} item={item} />
                    ))}
                  </div>
                )}
              </div>

              {/* Blacklist - 2 cols */}
              <div className="lg:col-span-2 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-lg flex items-center gap-2">
                    <UserX className="h-5 w-5 text-red-500" />
                    Danh sách đen
                    <Badge variant="destructive" className="ml-1">{blacklist.length}</Badge>
                  </h3>
                </div>
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input placeholder="Tìm kiếm blacklist..."
                    className="pl-9 h-9" value={searchBL} onChange={(e) => setSearchBL(e.target.value)} />
                </div>
                {blacklist.filter(b => !searchBL || b.name.toLowerCase().includes(searchBL.toLowerCase())).length === 0 ? (
                  <Card className="border-dashed border-red-200/50">
                    <CardContent className="py-12 flex flex-col items-center text-muted-foreground">
                      <UserX className="h-10 w-10 mb-3 opacity-30" />
                      <p>Danh sách đen trống</p>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-1 xl:grid-cols-2">
                    {blacklist
                      .filter(b => !searchBL || b.name.toLowerCase().includes(searchBL.toLowerCase()))
                      .map((item) => (
                        <BlacklistCard key={item.id} item={item} />
                      ))}
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          {/* ============================================================ */}
          {/* TAB 2: INTRUSION EVIDENCE                                     */}
          {/* ============================================================ */}
          <TabsContent value="evidence" className="mt-6 space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <Input type="date" className="w-44 h-9" value={dateFilter}
                  onChange={(e) => {
                    setDateFilter(e.target.value);
                    fetchIntrusionEvents(1, e.target.value);
                  }} />
                {dateFilter && (
                  <Button variant="ghost" size="sm" className="h-9 px-2"
                    onClick={() => { setDateFilter(""); fetchIntrusionEvents(1, ""); }}>
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <div className="text-sm text-muted-foreground">
                {eventsTotal} sự kiện{dateFilter ? ` ngày ${dateFilter}` : ""}
              </div>
            </div>

            {/* Events Grid */}
            {eventsLoading ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[1, 2, 3, 4, 5, 6].map(i => (
                  <Card key={i} className="overflow-hidden animate-pulse">
                    <div className="aspect-video bg-muted" />
                    <CardContent className="p-3 space-y-2">
                      <div className="h-4 bg-muted rounded w-3/4" />
                      <div className="h-3 bg-muted rounded w-1/2" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : events.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="py-16 flex flex-col items-center text-muted-foreground">
                  <Film className="h-12 w-12 mb-4 opacity-30" />
                  <p className="text-lg font-medium">Chưa có sự kiện xâm nhập</p>
                  <p className="text-sm mt-1">Hệ thống sẽ tự động ghi nhận khi phát hiện xâm nhập</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {events.map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
              </div>
            )}

            <Pagination page={eventsPage} totalPages={eventsTotalPages}
              onPageChange={(p) => { setEventsPage(p); fetchIntrusionEvents(p, dateFilter); }} />
          </TabsContent>
        </Tabs>
      </div>

      {/* ================================================================ */}
      {/* DIALOG: Alert Detail                                              */}
      {/* ================================================================ */}
      <Dialog open={!!selectedAlert} onOpenChange={(open) => !open && setSelectedAlert(null)}>
        <DialogContent className="sm:max-w-xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg text-red-600">
              <ShieldAlert className="h-5 w-5" /> Chi tiết phát hiện
            </DialogTitle>
          </DialogHeader>
          {selectedAlert && (
            <div className="space-y-4">
              <div className="rounded-lg overflow-hidden border">
                <img src={getImageUrl(selectedAlert.img)} alt="Detail"
                  className="w-full object-contain max-h-[300px] bg-black"
                  onError={(e: any) => { e.target.src = "https://placehold.co/600x400?text=Error"; }} />
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Trạng thái</span>
                  <div className="font-semibold mt-0.5">{selectedAlert.location}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Camera</span>
                  <div className="font-semibold mt-0.5">{selectedAlert.cam}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Ngày</span>
                  <div className="font-semibold mt-0.5">{selectedAlert.date}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Giờ</span>
                  <div className="font-semibold mt-0.5">{selectedAlert.time}</div>
                </div>
              </div>
              {selectedAlert.count > 1 && (
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-muted-foreground flex items-center gap-1">
                    <ImageIcon className="h-4 w-4" /> Lịch sử ({selectedAlert.count} lần)
                  </p>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {(selectedAlert.details || []).map((d, i) => (
                      <div key={i} className="flex items-center gap-3 p-2 rounded-lg border bg-muted/20">
                        <img src={getImageUrl(d.img)} alt="" className="w-16 h-16 rounded object-cover border"
                          onError={(e: any) => { e.target.src = "https://placehold.co/100?text=Error"; }} />
                        <div className="text-xs">
                          <div className="font-semibold">Lần {selectedAlert.count - i}</div>
                          <div className="text-muted-foreground">{d.time}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {selectedAlert.location !== "Đã xác minh" && (
                <div className="flex gap-2">
                  <Button className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                    onClick={() => { handleAddToBlacklist(selectedAlert); setSelectedAlert(null); }}>
                    <UserX className="mr-2 h-4 w-4" /> Thêm vào Blacklist
                  </Button>
                  <Button variant="outline" className="flex-1"
                    onClick={() => { handleVerifyAlert(selectedAlert.id); setSelectedAlert(null); }}>
                    <CheckCircle className="mr-2 h-4 w-4" /> Xác minh
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ================================================================ */}
      {/* DIALOG: Intrusion Event Detail + Video Player                     */}
      {/* ================================================================ */}
      <Dialog open={!!selectedEvent} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Film className="h-5 w-5 text-orange-500" /> Chi tiết sự kiện xâm nhập
              {selectedEvent && <AlertBadge level={selectedEvent.alert_level} />}
            </DialogTitle>
          </DialogHeader>
          {selectedEvent && (
            <div className="space-y-4">
              {/* Video Player */}
              <div className="rounded-lg overflow-hidden border bg-black">
                <video
                  key={selectedEvent.video_url}
                  src={selectedEvent.video_url}
                  controls
                  className="w-full aspect-video"
                  autoPlay
                />
              </div>

              {/* Video Info */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Camera</span>
                  <div className="font-semibold mt-0.5">{selectedEvent.cam_id.toUpperCase()}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Thời điểm</span>
                  <div className="font-semibold mt-0.5">{selectedEvent.timestamp}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Dung lượng</span>
                  <div className="font-semibold mt-0.5">{selectedEvent.size_mb} MB</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <span className="text-xs text-muted-foreground">Ảnh chụp</span>
                  <div className="font-semibold mt-0.5">{selectedEvent.snapshot_count} ảnh</div>
                </div>
              </div>

              {/* Download */}
              <a href={selectedEvent.video_url} download className="block">
                <Button variant="outline" className="w-full h-10">
                  <Download className="mr-2 h-4 w-4" /> Tải video ({selectedEvent.size_mb} MB)
                </Button>
              </a>

              {/* Snapshots Gallery */}
              {selectedEvent.snapshots.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm font-semibold flex items-center gap-2">
                    <ImageIcon className="h-4 w-4" /> Ảnh chụp tại thời điểm phát hiện
                  </p>
                  <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
                    {selectedEvent.snapshots.map((snap, i) => (
                      <div key={i} className="relative group rounded-lg overflow-hidden border">
                        <img src={snap.url} alt={`Snapshot ${i}`}
                          className="w-full aspect-square object-cover"
                          onError={(e: any) => { e.target.src = "https://placehold.co/200?text=Error"; }} />
                        <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-1.5 py-1 text-[10px] text-white">
                          {snap.person_id && <span>P{snap.person_id} • </span>}
                          {snap.time.split(" ")[1]}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
