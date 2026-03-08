import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Lock, Unlock, AlertOctagon, Thermometer, Server, Zap, Power } from "lucide-react";
import { useState } from "react";
import { toast } from "@/hooks/use-toast";

const doors = [
  { id: "D-01", name: "Cổng chính", status: "unlocked", type: "Kính đôi" },
  { id: "D-02", name: "Cửa nhận hàng sau", status: "locked", type: "Thép gia cố" },
  { id: "D-03", name: "Phòng nhân sự", status: "locked", type: "Tiêu chuẩn" },
  { id: "D-04", name: "Phòng giám đốc", status: "locked", type: "Sinh trắc học" },
];

export default function Doors() {
  const [relayActive, setRelayActive] = useState(false);

  const triggerRelay = () => {
    setRelayActive(true);
    toast({
      title: "Tín hiệu Relay đã gửi",
      description: "Đang kích hoạt cơ chế mở cửa (5s)...",
    });
    setTimeout(() => {
      setRelayActive(false);
    }, 5000);
  };

  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Cửa & Phòng máy chủ</h2>
            <p className="text-muted-foreground">Kiểm soát truy cập và giám sát môi trường</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant={relayActive ? "default" : "outline"}
              className={relayActive ? "bg-emerald-500 hover:bg-emerald-600 animate-pulse" : ""}
              onClick={triggerRelay}
            >
              <Zap className="mr-2 h-4 w-4" />
              {relayActive ? "Relay Đang hoạt động..." : "Kiểm tra Relay Cửa"}
            </Button>
            <Button variant="destructive">
              <AlertOctagon className="mr-2 h-4 w-4" />
              Khóa khẩn cấp
            </Button>
          </div>
        </div>

        {/* Server Room Highlight */}
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Card className="h-full border-primary/20 bg-primary/5">
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <Server className="h-5 w-5 text-primary" />
                  <CardTitle>Phòng máy chủ chính</CardTitle>
                </div>
                <div className="flex gap-2">
                  <Badge variant="outline" className="bg-primary/20 text-primary border-primary/50 animate-pulse">AN TOÀN</Badge>
                  {relayActive && (
                    <Badge variant="default" className="bg-emerald-500 animate-pulse">RELAY MỞ</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="relative aspect-[21/9] w-full overflow-hidden rounded-lg border bg-black">
                  <img
                    src="http://localhost:5000/video_feed/0"
                    alt="Server Room Camera"
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      setTimeout(() => {
                        (e.target as HTMLImageElement).src = `http://localhost:5000/video_feed/0?t=${Date.now()}`;
                      }, 2000);
                    }}
                  />
                  <div className="absolute top-2 left-2 bg-black/70 text-white px-2 py-1 rounded text-xs flex items-center gap-1">
                    <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
                    LIVE
                  </div>
                  <div className="absolute bottom-2 left-2 text-xs text-white bg-black/60 px-2 py-1 rounded">
                    CAM 1 — Webcam | Phòng máy chủ
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-background/50 p-3 rounded-lg border border-border/50">
                    <div className="text-xs text-muted-foreground mb-1">Nhiệt độ</div>
                    <div className="text-xl font-mono font-bold flex items-center gap-2">
                      <Thermometer className="h-4 w-4 text-emerald-500" />
                      20.1°C
                    </div>
                  </div>
                  <div className="bg-background/50 p-3 rounded-lg border border-border/50">
                    <div className="text-xs text-muted-foreground mb-1">Độ ẩm</div>
                    <div className="text-xl font-mono font-bold">42%</div>
                  </div>
                  <div className="bg-background/50 p-3 rounded-lg border border-border/50">
                    <div className="text-xs text-muted-foreground mb-1">Tải điện</div>
                    <div className="text-xl font-mono font-bold">12.4 kW</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-4">
            <h3 className="font-medium text-sm text-muted-foreground">Điểm truy cập</h3>
            {doors.map((door) => (
              <Card key={door.id} className="overflow-hidden">
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`h-10 w-10 rounded-full flex items-center justify-center ${door.status === 'locked' ? 'bg-red-500/10 text-red-500' : 'bg-emerald-500/10 text-emerald-500'}`}>
                      {door.status === 'locked' ? <Lock className="h-5 w-5" /> : <Unlock className="h-5 w-5" />}
                    </div>
                    <div>
                      <div className="font-medium">{door.name}</div>
                      <div className="text-xs text-muted-foreground font-mono">{door.id} • {door.type}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground">
                      <Power className="h-4 w-4" />
                    </Button>
                    <Switch checked={door.status === 'locked'} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}