import Layout from "@/components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DoorOpen,
  DoorClosed,
  Camera,
  ScanFace,
  Power,
  Zap,
  Shield,
  Timer,
} from "lucide-react";
import { useState } from "react";

/* =======================
   TYPES
======================= */
type DoorMode = "AUTO" | "MANUAL" | "LOCKDOWN";
type SecurityLevel = "SAFE" | "WARNING" | "DANGER";

type Door = {
  id: string;
  name: string;
  cameraId: number;
  enabled: boolean;
  status: "OPEN" | "CLOSED";
  mode: DoorMode;
  security: SecurityLevel;
  lastUser: string | null;
  openedSeconds: number;
};

/* =======================
   MOCK DATA
======================= */
const initialDoors: Door[] = [
  {
    id: "MAIN",
    name: "Cửa chính",
    cameraId: 0,
    enabled: true,
    status: "OPEN",
    mode: "AUTO",
    security: "SAFE",
    lastUser: "Nguyễn Thành Trung",
    openedSeconds: 42,
  },
  {
    id: "SIDE",
    name: "Cửa phụ",
    cameraId: 1,
    enabled: false,
    status: "CLOSED",
    mode: "MANUAL",
    security: "SAFE",
    lastUser: null,
    openedSeconds: 0,
  },
];

/* =======================
   CAMERA IMAGE COMPONENT
======================= */
function CameraImage({ door }: { door: Door }) {
  return (
    <div className="relative aspect-video overflow-hidden rounded-lg border bg-black">
      <img
        src={`http://localhost:5000/video_feed/${door.cameraId}`}
        alt={door.name}
        className="h-full w-full object-contain"
        onError={(e) => {
          setTimeout(() => {
            (e.target as HTMLImageElement).src = `http://localhost:5000/video_feed/${door.cameraId}?t=${Date.now()}`;
          }, 2000);
        }}
      />

      {/* LIVE */}
      <div className="absolute top-2 left-2 bg-black/70 text-white px-2 py-1 rounded text-xs flex items-center gap-1">
        <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
        LIVE
      </div>

      {/* STATUS */}
      <Badge
        className={`absolute top-2 right-2 ${door.status === "OPEN"
            ? "bg-emerald-500/90 text-white"
            : "bg-gray-700/90 text-white"
          }`}
      >
        {door.status}
      </Badge>

      {/* CAMERA LABEL */}
      <div className="absolute bottom-2 left-2 text-xs text-white bg-black/60 px-2 py-1 rounded">
        CAM-{door.cameraId} (Webcam)
      </div>
    </div>
  );
}

/* =======================
   MAIN PAGE
======================= */
export default function Gates() {
  const [doors, setDoors] = useState<Door[]>(initialDoors);

  const toggleDoor = (id: string) => {
    setDoors((prev) =>
      prev.map((d) => (d.id === id ? { ...d, enabled: !d.enabled } : d))
    );
  };

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(
      2,
      "0"
    )}`;

  const securityColor = (level: SecurityLevel) => {
    if (level === "SAFE") return "bg-emerald-500/10 text-emerald-500";
    if (level === "WARNING") return "bg-yellow-500/10 text-yellow-500";
    return "bg-red-500/10 text-red-500";
  };

  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <h2 className="text-3xl font-bold">Giám sát cửa ra vào</h2>

        {/* CAMERA GRID */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {doors.map((door) => (
            <Card key={door.id}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Camera className="h-5 w-5 text-primary" />
                  {door.name}
                </CardTitle>
              </CardHeader>

              <CardContent className="space-y-4">
                <CameraImage door={door} />

                <div className="flex justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <ScanFace className="h-4 w-4 text-primary" />
                    {door.lastUser ? (
                      <span>
                        AI: <b className="text-primary">{door.lastUser}</b>
                      </span>
                    ) : (
                      <span className="text-muted-foreground">
                        Chưa nhận diện
                      </span>
                    )}
                  </div>

                  <Badge
                    className={
                      door.status === "OPEN"
                        ? "bg-emerald-500/10 text-emerald-500"
                        : "bg-muted text-muted-foreground"
                    }
                  >
                    {door.status}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* DOOR CONTROL */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {doors.map((door) => (
            <Card key={door.id}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {door.status === "OPEN" ? (
                    <DoorOpen className="text-emerald-500" />
                  ) : (
                    <DoorClosed />
                  )}
                  {door.name}
                </CardTitle>
              </CardHeader>

              <CardContent className="space-y-4 text-sm">
                <div className="flex justify-between items-center">
                  <span>Kích hoạt cửa</span>
                  <Switch
                    checked={door.enabled}
                    onCheckedChange={() => toggleDoor(door.id)}
                  />
                </div>

                <div className="flex justify-between items-center">
                  <span>Chế độ</span>
                  <Badge variant="outline">{door.mode}</Badge>
                </div>

                <div className="flex justify-between items-center">
                  <span>An ninh</span>
                  <Badge className={securityColor(door.security)}>
                    <Shield className="h-3 w-3 mr-1" />
                    {door.security}
                  </Badge>
                </div>

                <div className="flex justify-between items-center">
                  <span>Thời gian mở</span>
                  <span className="font-mono flex items-center gap-1 text-muted-foreground">
                    <Timer className="h-4 w-4" />
                    {door.status === "OPEN"
                      ? formatTime(door.openedSeconds)
                      : "--:--"}
                  </span>
                </div>

                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    disabled={!door.enabled}
                    className="flex-1"
                  >
                    <Zap className="h-4 w-4 mr-2" />
                    Test Relay
                  </Button>

                  <Button
                    variant="secondary"
                    disabled={!door.enabled}
                    className="flex-1"
                  >
                    <Power className="h-4 w-4 mr-2" />
                    Mở thử
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </Layout>
  );
}
