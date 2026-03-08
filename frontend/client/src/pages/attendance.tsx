import Layout from "@/components/Layout";
import CameraFeed from "@/components/CameraFeed";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileSpreadsheet, ScanFace } from "lucide-react";

// Nếu anh không dùng ảnh tĩnh nữa thì có thể bỏ import này, nhưng em cứ để đây cho đỡ lỗi file
import cctvEntrance from "@assets/generated_images/cctv_office_entrance.png";
import cctvHallway from "@assets/generated_images/cctv_hallway.png";

// Dữ liệu mẫu (Sau này anh có thể thay bằng API thật từ Python trả về)
const logs = [
  {
    id: 1,
    time: "11:05:23",
    user: "Trần Minh Tuấn",
    location: "Sảnh Lễ Tân (Gate 1)",
    method: "FaceID AI",
    status: "Hợp lệ",
  },
  {
    id: 2,
    time: "11:02:45",
    user: "Nguyễn Thu Hà",
    location: "Thang máy Tầng 12",
    method: "Thẻ từ NV",
    status: "Hợp lệ",
  },
  {
    id: 3,
    time: "10:58:10",
    user: "Unknown (Người lạ)",
    location: "Cửa thoát hiểm B2",
    method: "Cảm biến hồng ngoại",
    status: "Cảnh báo",
  },
  {
    id: 4,
    time: "10:55:00",
    user: "Lê Văn Hùng",
    location: "Phòng Server",
    method: "Vân tay + PIN",
    status: "Từ chối",
  },
  {
    id: 5,
    time: "10:45:30",
    user: "Phạm Thị Lan",
    location: "Cổng kiểm soát xe",
    method: "Biển số (LPR)",
    status: "Hợp lệ",
  },
];

export default function Attendance() {
  return (
    <Layout>
      <div className="flex flex-col gap-8">
        {/* --- HEADER --- */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              Trung tâm Kiểm soát An ninh
            </h2>
            <p className="text-muted-foreground">
              Hệ thống giám sát ra vào và chấm công sinh trắc học thông minh
            </p>
          </div>
          <Button variant="outline">
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            Xuất báo cáo
          </Button>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* --- CỘT TRÁI: CAMERA FEEDS --- */}
          <div className="space-y-4">
            <h3 className="font-medium text-sm flex items-center gap-2">
              <ScanFace className="h-4 w-4 text-primary" />
              Camera Giám sát (AI Live View)
            </h3>

            {/* CAMERA 1: Kết nối Python Feed 0 */}
            <CameraFeed
              useWebcam={false}
              src="http://localhost:5000/video_feed/0"
              label="CAM-01: Cổng Chính (FaceID)"
              location="Khu vực Check-in nhận diện khuôn mặt"
              className="aspect-video shadow-xl border-primary/20"
            />

            {/* CAMERA 2: Kết nối Python Feed 1 */}
            <CameraFeed
              useWebcam={false}
              src="http://localhost:5000/video_feed/1"
              label="CAM-02: Hành Lang / Văn Phòng"
              location="Khu vực Giám sát chung"
              className="aspect-video shadow-xl"
            />
          </div>

          {/* --- CỘT PHẢI: LOGS --- */}
          <Card className="h-full flex flex-col">
            <CardHeader>
              <CardTitle>Nhật ký Sự kiện (Event Logs)</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Thời gian</TableHead>
                    <TableHead>Đối tượng</TableHead>
                    <TableHead>Vị trí</TableHead>
                    <TableHead>Phương thức</TableHead>
                    <TableHead>Kết quả</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {log.time}
                      </TableCell>
                      <TableCell className="font-medium">{log.user}</TableCell>
                      <TableCell>{log.location}</TableCell>
                      <TableCell className="text-xs">{log.method}</TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            log.status === "Hợp lệ" ? "outline" : "destructive"
                          }
                          className={
                            log.status === "Hợp lệ"
                              ? "text-emerald-500 border-emerald-500/20 bg-emerald-500/10"
                              : ""
                          }
                        >
                          {log.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  );
}
