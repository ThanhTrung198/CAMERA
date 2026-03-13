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
  Calendar,
  AlertOctagon,
  X,
  Shield,
  Film,
  UserPlus
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const API = "http://localhost:5000";

// --- TYPES ---
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

export default function Security() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [blacklist, setBlacklist] = useState<BlacklistItem[]>([]);
  const [events, setEvents] = useState<IntrusionEvent[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  
  // Dialog selection states
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<IntrusionEvent | null>(null);

  // Stats
  const [eventsTotal, setEventsTotal] = useState(0);

  // API Utilities
  const getImageUrl = (path: string) => {
    if (!path || path === "") return "https://placehold.co/600x400?text=No+Image";
    if (path.startsWith("http")) return path;
    let cleanPath = path.replace(/\\/g, "/");
    if (!cleanPath.startsWith("/")) cleanPath = "/" + cleanPath;
    return `${API}${cleanPath}`;
  };

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/security/alerts`);
      const data = await res.json();
      setAlerts(data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchBlacklist = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/security/blacklist`);
      const data = await res.json();
      setBlacklist(data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchIntrusionEvents = useCallback(async (date = "") => {
    try {
      let url = `${API}/api/security/intrusion-events?page=1&per_page=20`;
      if (date) url += `&date=${date}`;
      const res = await fetch(url);
      const data = await res.json();
      setEvents(data.events || []);
      setEventsTotal(data.total || 0);
    } catch (e) { console.error(e); }
  }, []);

  const refreshAll = async () => {
    setLoading(true);
    await Promise.all([fetchAlerts(), fetchBlacklist(), fetchIntrusionEvents(dateFilter)]);
    setLoading(false);
  };

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 10000);
    return () => clearInterval(interval);
  }, []);

  // Action Handlers
  const handleAddToBlacklist = async (item: AlertItem) => {
    try {
      await fetch(`${API}/api/security/blacklist/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `Đối tượng không xác định`,
          reason: `Phát hiện nghi vấn tại ${item.cam}`,
          image: item.img,
        }),
      });
      refreshAll();
      setSelectedAlert(null);
    } catch (e) { console.error(e); }
  };

  const handleDeleteBlacklist = async (id: number) => {
    if (!confirm("Xóa đối tượng này khỏi danh sách đen?")) return;
    try {
      await fetch(`${API}/api/security/blacklist/${id}`, { method: "DELETE" });
      fetchBlacklist();
    } catch (e) { console.error(e); }
  };

  const handleVerifyAlert = async (id: number) => {
    try {
      await fetch(`${API}/api/security/alerts/${id}/verify`, { method: "PUT" });
      fetchAlerts();
      setSelectedAlert(null);
    } catch (e) { console.error(e); }
  };

  return (
    <Layout>
      <div className="flex flex-col gap-6">
        
        {/* HEADER & QUICK STATS */}
        <div className="flex flex-col lg:flex-row justify-between gap-4 shrink-0 bg-white dark:bg-slate-900 border border-border p-5 rounded-2xl shadow-sm">
          <div>
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <Shield className="h-7 w-7 text-red-500" />
              Trung tâm An Ninh
            </h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Kiểm soát người lạ, đối tượng trong danh sách đen và bằng chứng xâm nhập.
            </p>
          </div>
          <div className="flex items-center gap-4">
              <div className="flex items-center gap-4 border-r border-border pr-6">
                <div className="flex flex-col items-end">
                   <span className="text-2xl font-bold text-red-600">
                     {alerts.filter(a => a.location?.includes("GIA_MAO")).length}
                   </span>
                   <span className="text-[10px] font-bold uppercase text-muted-foreground tracking-wider">Giả mạo</span>
                </div>
                <div className="flex flex-col items-end">
                   <span className="text-2xl font-bold text-amber-500">
                     {alerts.filter(a => !a.location?.includes("GIA_MAO")).length}
                   </span>
                   <span className="text-[10px] font-bold uppercase text-muted-foreground tracking-wider">Người lạ</span>
                </div>
                <div className="flex flex-col items-end">
                   <span className="text-2xl font-bold text-red-500">{blacklist.length}</span>
                   <span className="text-[10px] font-bold uppercase text-muted-foreground tracking-wider">Mối đe dọa</span>
                </div>
                <div className="flex flex-col items-end">
                   <span className="text-2xl font-bold text-orange-500">{eventsTotal}</span>
                   <span className="text-[10px] font-bold uppercase text-muted-foreground tracking-wider">Sự kiện quay lại</span>
                </div>
              </div>
             <Button variant="outline" size="icon" onClick={refreshAll} disabled={loading} className={loading ? "animate-spin" : ""}>
               <RefreshCw className="h-4 w-4" />
             </Button>
          </div>
        </div>

        {/* MAIN TABS */}
        <Tabs defaultValue="alerts" className="w-full">
          <TabsList className="h-12 w-full max-w-md grid grid-cols-2 p-1 bg-muted/50 rounded-lg">
            <TabsTrigger value="alerts" className="rounded-md font-medium text-sm">Cảnh báo Thời gian thực</TabsTrigger>
            <TabsTrigger value="blacklist" className="rounded-md font-medium text-sm">Quản lý Rủi ro</TabsTrigger>
          </TabsList>

          {/* TAB 1: ALERTS & REAL-TIME */}
          <TabsContent value="alerts" className="mt-6 space-y-10">
            
            {/* SECTION: SPOOFING DETECTION (Cảnh báo Giả mạo) */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-black flex items-center gap-2 text-red-600 dark:text-red-400">
                   <ShieldAlert className="h-6 w-6 animate-pulse" /> Phát hiện Giả mạo (Anti-Spoofing)
                </h3>
                <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200">Ưu tiên cao</Badge>
              </div>

              {alerts.filter(a => a.location?.includes("GIA_MAO")).length === 0 ? (
                 <div className="bg-slate-50 dark:bg-slate-800/30 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center">
                    <CheckCircle className="h-8 w-8 text-emerald-500 mx-auto mb-2 opacity-50" />
                    <p className="text-sm font-bold text-slate-500">Chưa phát hiện hành vi giả mạo nào.</p>
                 </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                   {alerts.filter(a => a.location?.includes("GIA_MAO")).map(item => (
                      <Card key={item.id} className="overflow-hidden border-2 border-red-500 shadow-lg shadow-red-500/10 transition-all hover:-translate-y-1" onClick={() => setSelectedAlert(item)}>
                        <div className="aspect-[4/3] bg-muted relative">
                           <img src={getImageUrl(item.img)} alt="Spoof" className="w-full h-full object-cover" />
                           <div className="absolute top-2 left-2 flex flex-col gap-1">
                              <Badge className="bg-red-600 text-white border-none font-black animate-bounce">
                                <AlertOctagon className="w-3 h-3 mr-1" /> GIẢ MẠO
                              </Badge>
                              <Badge className="bg-black/60 text-white backdrop-blur-sm border-none text-[9px]">
                                {item.location.replace("GIA_MAO_", "")}
                              </Badge>
                           </div>
                           <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-3 pt-8 flex justify-between items-end">
                              <span className="text-white text-[10px] font-bold flex items-center gap-1"><Camera className="w-3 h-3" /> {item.cam}</span>
                              <span className="text-white text-[10px] font-mono">{item.time}</span>
                           </div>
                        </div>
                        <CardContent className="p-3 bg-red-50/50 dark:bg-red-950/10 flex gap-2">
                           <Button size="sm" variant="destructive" className="w-full text-xs font-bold" onClick={(e) => { e.stopPropagation(); handleAddToBlacklist(item); }}>
                              <UserX className="w-3 h-3 mr-1" /> Chặn ngay lập tức
                           </Button>
                        </CardContent>
                      </Card>
                   ))}
                </div>
              )}
            </div>

            <hr className="border-slate-200 dark:border-slate-800" />

            {/* SECTION: STRANGER DETECTION (Người lạ) */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold flex items-center gap-2">
                   <AlertTriangle className="h-5 w-5 text-amber-500" /> Phát hiện Người Lạ
                </h3>
              </div>

              {alerts.filter(a => !a.location?.includes("GIA_MAO")).length === 0 ? (
                 <div className="border border-dashed border-border rounded-xl p-12 flex flex-col items-center justify-center text-muted-foreground">
                   <ShieldAlert className="h-10 w-10 mb-3 opacity-20" />
                   <p className="font-medium">Khuôn viên an toàn</p>
                   <p className="text-sm">Hiện không có đối tượng lạ nào xâm nhập.</p>
                 </div>
              ) : (
                 <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                   {alerts.filter(a => !a.location?.includes("GIA_MAO")).map(item => {
                     const isVerified = item.location === "Đã xác minh";
                     return (
                       <Card key={item.id} className={`overflow-hidden cursor-pointer border-t-4 transition-all hover:-translate-y-1 hover:shadow-lg ${isVerified ? 'border-t-emerald-500' : 'border-t-amber-500'}`} onClick={() => setSelectedAlert(item)}>
                          <div className="aspect-[4/3] bg-muted relative">
                             <img src={getImageUrl(item.img)} alt="Alert" className="w-full h-full object-cover" />
                             <Badge variant={isVerified ? "outline" : "destructive"} className={`absolute top-2 left-2 truncate max-w-[120px] ${isVerified ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : ''}`}>
                               {isVerified ? "Đã duyệt" : item.location || "Chưa rõ"}
                             </Badge>
                             <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3 pt-8 flex justify-between items-end">
                                <span className="text-white text-xs font-mono flex items-center gap-1"><Camera className="w-3 h-3" /> {item.cam}</span>
                                <span className="text-white text-[10px]">{item.time}</span>
                             </div>
                          </div>
                          {!isVerified && (
                             <CardContent className="p-3 bg-card flex gap-2">
                                <Button size="sm" variant="outline" className="flex-1 text-xs h-8 border-emerald-200 text-emerald-600 hover:bg-emerald-50" onClick={(e) => { e.stopPropagation(); handleVerifyAlert(item.id); }}>
                                   <CheckCircle className="w-3 h-3 mr-1" /> Bỏ qua
                                </Button>
                                <Button size="sm" variant="destructive" className="flex-1 text-xs h-8" onClick={(e) => { e.stopPropagation(); handleAddToBlacklist(item); }}>
                                   <UserX className="w-3 h-3 mr-1" /> Chặn
                                </Button>
                             </CardContent>
                          )}
                       </Card>
                     )
                   })}
                 </div>
              )}
            </div>
            
            <hr className="border-border my-8" />
            
            {/* INTRUSION EVENTS PREVIEW ROW */}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold flex items-center gap-2">
                 <Video className="h-5 w-5 text-orange-500" /> Bằng chứng Video (Tự động lưu)
              </h3>
              <div className="flex items-center gap-2">
                 <Input type="date" className="w-40 h-9 text-sm" value={dateFilter} onChange={(e) => { setDateFilter(e.target.value); fetchIntrusionEvents(e.target.value); }} />
                 {dateFilter && <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => { setDateFilter(""); fetchIntrusionEvents(""); }}><X className="w-4 h-4" /></Button>}
              </div>
            </div>

            {events.length === 0 ? (
               <div className="bg-muted/30 rounded-xl p-8 text-center text-muted-foreground border border-border">
                 Chưa có dữ liệu video xâm nhập.
               </div>
            ) : (
               <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                 {events.slice(0, 6).map(event => (
                   <div key={event.id} className="relative group rounded-xl overflow-hidden border border-border cursor-pointer bg-black/90 aspect-video" onClick={() => setSelectedEvent(event)}>
                     {event.thumbnail ? (
                        <img src={event.thumbnail} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" alt="Thumb" />
                     ) : (
                        <div className="w-full h-full flex items-center justify-center"><Film className="w-8 h-8 text-white/20" /></div>
                     )}
                     <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center">
                        <Play className="w-10 h-10 text-white opacity-0 group-hover:opacity-100 drop-shadow-lg" />
                     </div>
                     <div className="absolute top-2 left-2 flex gap-1">
                        <Badge variant="destructive" className="text-[10px] uppercase">{event.alert_level === 'high' ? 'Cao' : event.alert_level}</Badge>
                     </div>
                     <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 px-3 py-2 flex justify-between items-center text-white">
                        <span className="text-xs font-medium truncate max-w-[150px]">{event.cam_id.toUpperCase()}</span>
                        <span className="text-[10px] text-white/70">{event.time}</span>
                     </div>
                   </div>
                 ))}
               </div>
            )}
            
          </TabsContent>

          {/* TAB 2: BLACKLIST & HISTORY */}
          <TabsContent value="blacklist" className="mt-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                 <h3 className="text-lg font-bold flex items-center gap-2">
                    <AlertOctagon className="h-5 w-5 text-red-500" /> Danh sách đen
                 </h3>
                 <p className="text-sm text-muted-foreground">Các đối tượng bị cấm vào khuôn viên trường.</p>
              </div>
              <div className="relative w-72">
                 <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" />
                 <Input placeholder="Tìm kiếm đối tượng..." className="pl-9 h-9" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
              </div>
            </div>

            <div className="bg-white dark:bg-slate-900 rounded-xl border border-border overflow-hidden">
               {blacklist.filter(b => !searchQuery || b.name.toLowerCase().includes(searchQuery.toLowerCase())).length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">Không có hồ sơ nào.</div>
               ) : (
                  <div className="divide-y divide-border">
                     {blacklist.filter(b => !searchQuery || b.name.toLowerCase().includes(searchQuery.toLowerCase())).map(item => (
                        <div key={item.id} className="p-4 flex flex-col sm:flex-row gap-4 items-start sm:items-center hover:bg-muted/30 transition-colors">
                           <div className="h-16 w-16 rounded-md border-2 border-red-500/30 overflow-hidden shrink-0">
                              <img src={getImageUrl(item.img)} alt="BL" className="w-full h-full object-cover" />
                           </div>
                           <div className="flex-1">
                              <h4 className="font-bold text-red-600 dark:text-red-400 text-sm">{item.name}</h4>
                              <p className="text-xs text-muted-foreground mt-0.5">{item.reason}</p>
                              <div className="flex gap-3 text-[10px] text-muted-foreground mt-2 font-mono">
                                 <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> Ngày thêm: {item.date}</span>
                                 <span>•</span>
                                 <span>ID: BL-{item.id}</span>
                              </div>
                           </div>
                           <Button variant="outline" size="sm" className="h-8 text-xs shrink-0 hover:bg-red-50 hover:text-red-600" onClick={() => handleDeleteBlacklist(item.id)}>
                              <Trash2 className="w-3 h-3 mr-1" /> Xóa thẻ phạt
                           </Button>
                        </div>
                     ))}
                  </div>
               )}
            </div>
          </TabsContent>
        </Tabs>

      </div>

      {/* --- DIALOGS --- */}

      {/* Alert Detail Dialog */}
      <Dialog open={!!selectedAlert} onOpenChange={(open) => !open && setSelectedAlert(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Chi tiết người lạ</DialogTitle>
          </DialogHeader>
          {selectedAlert && (
            <div className="space-y-4">
              <img src={getImageUrl(selectedAlert.img)} className="w-full h-48 object-cover rounded-lg border border-border" alt="Detail" />
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-muted p-2 rounded-md"><span className="text-xs text-muted-foreground block">Camera</span><span className="font-medium">{selectedAlert.cam}</span></div>
                <div className="bg-muted p-2 rounded-md"><span className="text-xs text-muted-foreground block">Vị trí</span><span className="font-medium">{selectedAlert.location || "Người lạ"}</span></div>
                <div className="bg-muted p-2 rounded-md"><span className="text-xs text-muted-foreground block">Lúc</span><span className="font-medium">{selectedAlert.time}</span></div>
                <div className="bg-muted p-2 rounded-md"><span className="text-xs text-muted-foreground block">Số lần quét</span><span className="font-medium">{selectedAlert.count} lần</span></div>
              </div>
              {selectedAlert.location !== "Đã xác minh" && (
                <div className="flex gap-2 pt-2">
                  <Button variant="outline" className="flex-1 border-emerald-200 text-emerald-600 hover:bg-emerald-50" onClick={() => handleVerifyAlert(selectedAlert.id)}>
                    <CheckCircle className="w-4 h-4 mr-2" /> Duyệt an toàn
                  </Button>
                  <Button variant="destructive" className="flex-1" onClick={() => handleAddToBlacklist(selectedAlert)}>
                    <UserPlus className="w-4 h-4 mr-2" /> Vào danh sách đen
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Event Player Dialog */}
      <Dialog open={!!selectedEvent} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <DialogContent className="sm:max-w-2xl bg-black border-border/50 text-white p-0 overflow-hidden">
          {selectedEvent && (
            <div className="flex flex-col">
              <video src={selectedEvent.video_url} controls autoPlay className="w-full aspect-video bg-black" />
              <div className="p-4 bg-slate-900 border-t border-slate-800">
                 <div className="flex items-center justify-between">
                    <div>
                       <h4 className="font-mono text-sm">{selectedEvent.cam_id.toUpperCase()}</h4>
                       <p className="text-xs text-slate-400 mt-1">{selectedEvent.timestamp}</p>
                    </div>
                    <a href={selectedEvent.video_url} download>
                      <Button size="sm" variant="secondary" className="h-8">
                         <Download className="w-3 h-3 mr-2" /> Tải về ({selectedEvent.size_mb}MB)
                      </Button>
                    </a>
                 </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      
    </Layout>
  );
}
