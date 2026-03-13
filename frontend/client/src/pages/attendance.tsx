import Layout from "@/components/Layout";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Users,
  CheckCircle2,
  Clock,
  UserX,
  AlertTriangle,
  Search,
  BookOpen,
  Filter
} from "lucide-react";

// --- MOCK DATA ---
const mockClasses = [
  {
    id: "20CT111",
    name: "Lớp 20CT111",
    department: "Khoa CNTT",
    room: "Phòng A.101",
    stats: {
      total: 40,
      present: 35,
      late: 2,
      absent: 3,
      stranger: 1,
    },
  },
  {
    id: "21KT112",
    name: "Lớp 21KT112",
    department: "Khoa Kinh Tế",
    room: "Phòng B.205",
    stats: {
      total: 50,
      present: 48,
      late: 0,
      absent: 2,
      stranger: 0,
    },
  },
  {
    id: "19NN113",
    name: "Lớp 19NN113",
    department: "Khoa Ngoại Ngữ",
    room: "Phòng C.302",
    stats: {
      total: 35,
      present: 35,
      late: 0,
      absent: 0,
      stranger: 2,
    },
  },
];

const mockStudents = {
  "20CT111": [
    { id: 1, mssv: "201A030123", name: "Nguyễn Trung Hiếu", status: "Co_Mat", time: "07:15:23", isStranger: false },
    { id: 2, mssv: "201A030124", name: "Trần Mai Anh", status: "Vao_Tre", time: "07:35:10", isStranger: false },
    { id: 3, mssv: "201A030125", name: "Lê Hoàng Khoa", status: "Vang_Mat", time: "---", isStranger: false },
    { id: 4, mssv: "UNKNOWN", name: "Không xác định", status: "Nguoi_La", time: "07:22:10", isStranger: true },
    { id: 5, mssv: "201A030126", name: "Phạm Văn Thiện", status: "Co_Mat", time: "07:10:05", isStranger: false },
  ],
  "21KT112": [
    { id: 6, mssv: "211A041099", name: "Trần Thị Mai", status: "Co_Mat", time: "07:20:00", isStranger: false },
    { id: 7, mssv: "211A041100", name: "Ngô Văn Hùng", status: "Vang_Mat", time: "---", isStranger: false },
  ],
  "19NN113": [
    { id: 8, mssv: "UNKNOWN", name: "Đeo khẩu trang che kín", status: "Nguoi_La", time: "08:05:12", isStranger: true },
    { id: 9, mssv: "UNKNOWN", name: "Người ngoài vào lớp", status: "Nguoi_La", time: "08:15:44", isStranger: true },
    { id: 10, mssv: "191A011001", name: "Lê Thị Bích", status: "Co_Mat", time: "06:55:00", isStranger: false },
  ]
};

const statusConfig: Record<string, { label: string; className: string }> = {
  Co_Mat: { label: "Có mặt", className: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
  Vao_Tre: { label: "Vào trễ", className: "bg-amber-500/10 text-amber-500 border-amber-500/20" },
  Vang_Mat: { label: "Vắng mặt", className: "bg-slate-500/10 text-slate-500 border-slate-500/20" },
  Nguoi_La: { label: "Người lạ", className: "bg-red-500/10 text-red-500 border-red-500/20 animate-pulse" },
};

export default function Attendance() {
  const [selectedClass, setSelectedClass] = useState(mockClasses[0].id);
  const [searchTerm, setSearchTerm] = useState("");

  const currentClassData = mockClasses.find(c => c.id === selectedClass);
  const currentStudents = mockStudents[selectedClass as keyof typeof mockStudents] || [];

  const filteredStudents = currentStudents.filter(std => 
    std.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    std.mssv.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <Layout>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Điểm danh theo Lớp</h2>
            <p className="text-muted-foreground mt-1">
              Kiểm soát quân số, phát hiện sinh viên vắng, đi trễ hoặc người lạ xâm nhập vào lớp học.
            </p>
          </div>
        </div>

        {/* --- DANH SÁCH LỚP HỌC KHUNG TRÊN CÙNG --- */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {mockClasses.map((cls) => (
            <Card 
              key={cls.id} 
              className={`cursor-pointer transition-all hover:border-primary/50 hover:shadow-md ${selectedClass === cls.id ? 'border-primary ring-1 ring-primary shadow-md bg-primary/5' : ''}`}
              onClick={() => setSelectedClass(cls.id)}
            >
              <CardContent className="p-5">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                      <BookOpen className="w-5 h-5 text-primary" />
                      {cls.name}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1">{cls.department} &bull; {cls.room}</p>
                  </div>
                  <Badge variant="secondary" className="font-mono text-xs">
                    Sĩ số: {cls.stats.total}
                  </Badge>
                </div>

                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                  <div className="flex flex-col items-center bg-emerald-500/10 rounded-md p-2 border border-emerald-500/10">
                    <span className="font-bold text-emerald-600 dark:text-emerald-400 text-lg">{cls.stats.present}</span>
                    <span className="text-emerald-600/80 dark:text-emerald-400/80 mt-1 line-clamp-1">Có mặt</span>
                  </div>
                  <div className="flex flex-col items-center bg-amber-500/10 rounded-md p-2 border border-amber-500/10">
                    <span className="font-bold text-amber-600 dark:text-amber-400 text-lg">{cls.stats.late}</span>
                    <span className="text-amber-600/80 dark:text-amber-400/80 mt-1 line-clamp-1">Vào trễ</span>
                  </div>
                  <div className="flex flex-col items-center bg-slate-500/10 rounded-md p-2 border border-slate-500/10">
                    <span className="font-bold text-slate-600 dark:text-slate-400 text-lg">{cls.stats.absent}</span>
                    <span className="text-slate-600/80 dark:text-slate-400/80 mt-1 line-clamp-1">Vắng</span>
                  </div>
                  <div className="flex flex-col items-center bg-red-500/10 rounded-md p-2 border border-red-500/20">
                    <span className="font-bold text-red-600 dark:text-red-400 text-lg">{cls.stats.stranger}</span>
                    <span className="text-red-600/80 dark:text-red-400/80 mt-1 line-clamp-1">Người lạ</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* --- DANH SÁCH CHI TIẾT CỦA LỚP ĐƯỢC CHỌN --- */}
        {currentClassData && (
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-border shadow-sm flex flex-col overflow-hidden">
            <div className="p-5 border-b border-border bg-slate-50/50 dark:bg-slate-800/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                 <h3 className="text-lg font-bold text-foreground">
                    Chi tiết điểm danh: <span className="text-primary">{currentClassData.name}</span>
                 </h3>
                 <p className="text-sm text-muted-foreground mt-0.5">Thời gian thực tế ghi nhận qua Camera AI trước cửa phòng học.</p>
              </div>
              
              <div className="flex items-center gap-2">
                <div className="relative w-64">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Tìm sinh viên, MSSV..."
                    className="pl-9 h-9 text-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <Button variant="outline" size="icon" className="h-9 w-9">
                  <Filter className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="overflow-auto max-h-[500px]">
              <Table>
                <TableHeader className="bg-muted/50 sticky top-0 z-10">
                  <TableRow>
                    <TableHead>Sinh Viên / Đối Tượng</TableHead>
                    <TableHead>MSSV</TableHead>
                    <TableHead>Giờ Ghi Nhận</TableHead>
                    <TableHead className="text-right">Trạng thái</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredStudents.map((std) => (
                    <TableRow key={std.id} className={std.status === "Nguoi_La" ? "bg-red-50/50 dark:bg-red-950/10 hover:bg-red-50 dark:hover:bg-red-950/20" : "hover:bg-muted/20"}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className={`h-9 w-9 border ${std.status === "Nguoi_La" ? "border-red-500" : "border-border"}`}>
                            <AvatarImage src={std.mssv === 'UNKNOWN' ? '' : `https://api.dicebear.com/7.x/notionists/svg?seed=${std.mssv}`} />
                            <AvatarFallback className={std.status === "Nguoi_La" ? "bg-red-100 text-red-600" : "bg-secondary"}>
                              {std.isStranger ? <AlertTriangle className="w-5 h-5" /> : 'SV'}
                            </AvatarFallback>
                          </Avatar>
                          <span className={`font-semibold ${std.status === "Nguoi_La" ? "text-red-600 dark:text-red-400" : "text-foreground"}`}>
                            {std.name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {std.isStranger ? (
                          <span className="text-xs text-red-500 font-bold bg-red-100 dark:bg-red-900/30 px-2 py-1 rounded">CẢNH BÁO</span>
                        ) : (
                          <span className="font-mono text-muted-foreground">{std.mssv}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {std.time === "---" ? (
                          <span className="text-muted-foreground/60">Chưa ghi nhận</span>
                        ) : (
                          <span className="font-mono font-medium">{std.time}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge
                          variant="outline"
                          className={statusConfig[std.status]?.className || ""}
                        >
                          {statusConfig[std.status]?.label || std.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                  
                  {filteredStudents.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                        Không tìm thấy sinh viên nào.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
