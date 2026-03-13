import Layout from "@/components/Layout";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Search,
  Plus,
  Filter,
  MoreHorizontal,
  Eye,
  Pencil,
  Trash2,
  Upload,
  User,
  Phone,
  Building2,
  GraduationCap,
  Users,
  Mail,
  BookOpen
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { useState } from "react";

const statusMap: Record<string, string> = {
  Dang_Hoc: "Đang học",
  Bao_Luu: "Bảo lưu",
  Da_Hoc_Xong: "Đã tốt nghiệp",
};

// Mock data
const mockStudents = [
  {
    id: 1,
    mssv: "201A030123",
    ho_ten: "Nguyễn Trung Hiếu",
    email: "hieunt201@vhu.edu.vn",
    sdt: "0901234567",
    khoa: "Khoa CNTT",
    lop: "20CT111",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Nguyễn Văn Hùng",
    sdt_giam_ho: "0987654321",
  },
  {
    id: 2,
    mssv: "211A041099",
    ho_ten: "Trần Thị Mai",
    email: "maitt211@vhu.edu.vn",
    sdt: "0912345678",
    khoa: "Khoa Kinh Tế",
    lop: "21KT112",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Trần Văn Bảy",
    sdt_giam_ho: "0918273645",
  },
  {
    id: 3,
    mssv: "191A011001",
    ho_ten: "Lê Hoàng Khoa",
    email: "khoalh191@vhu.edu.vn",
    sdt: "0923456789",
    khoa: "Khoa Ngoại Ngữ",
    lop: "19NN113",
    trang_thai: "Bao_Luu",
    nguoi_giam_ho: "Lê Văn Tám",
    sdt_giam_ho: "0928374655",
  },
  {
    id: 4,
    mssv: "221A050111",
    ho_ten: "Phạm Thu Hương",
    email: "huongpt221@vhu.edu.vn",
    sdt: "0934567890",
    khoa: "Khoa Du Lịch",
    lop: "22DL114",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Phạm Văn Chín",
    sdt_giam_ho: "0939485766",
  },
  {
    id: 5,
    mssv: "201A030222",
    ho_ten: "Vũ Hải Đăng",
    email: "dangvh201@vhu.edu.vn",
    sdt: "0945678901",
    khoa: "Khoa CNTT",
    lop: "20CT111",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Vũ Trọng Phụng",
    sdt_giam_ho: "0940596877",
  },
  {
    id: 6,
    mssv: "181A020333",
    ho_ten: "Đinh Thái Sơn",
    email: "sondt181@vhu.edu.vn",
    sdt: "0956789012",
    khoa: "Khoa Xã Hội",
    lop: "18XH115",
    trang_thai: "Da_Hoc_Xong",
    nguoi_giam_ho: "Đinh Bộ Lĩnh",
    sdt_giam_ho: "0951607988",
  },
  {
    id: 7,
    mssv: "211A041123",
    ho_ten: "Bùi Ngọc Yến",
    email: "yenbn211@vhu.edu.vn",
    sdt: "0967890123",
    khoa: "Khoa Kinh Tế",
    lop: "21KT112",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Bùi Văn Mười",
    sdt_giam_ho: "0962718099",
  },
  {
    id: 8,
    mssv: "201A030456",
    ho_ten: "Lý Gia Thành",
    email: "thanhlg201@vhu.edu.vn",
    sdt: "0978901234",
    khoa: "Khoa CNTT",
    lop: "20CT112",
    trang_thai: "Bao_Luu",
    nguoi_giam_ho: "Lý Công Uẩn",
    sdt_giam_ho: "0973829100",
  },
  {
    id: 9,
    mssv: "221A060789",
    ho_ten: "Hồ Anh Tuấn",
    email: "tuanha221@vhu.edu.vn",
    sdt: "0989012345",
    khoa: "Khoa Luật",
    lop: "22LU116",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Hồ Xuân Hương",
    sdt_giam_ho: "0984930211",
  },
  {
    id: 10,
    mssv: "231A070999",
    ho_ten: "Ngô Quyền",
    email: "quyenn231@vhu.edu.vn",
    sdt: "0990123456",
    khoa: "Khoa Lịch Sử",
    lop: "23LS117",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "Ngô Nhật Khánh",
    sdt_giam_ho: "0995041322",
  }
];

export default function Students() {
  const [students, setStudents] = useState(mockStudents);
  const [editingStd, setEditingStd] = useState<any>(null);
  const [viewingStd, setViewingStd] = useState<any>(null);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  const [newStd, setNewStd] = useState<any>({
    mssv: "",
    ho_ten: "",
    email: "",
    sdt: "",
    khoa: "",
    lop: "",
    trang_thai: "Dang_Hoc",
    nguoi_giam_ho: "",
    sdt_giam_ho: "",
  });

  const filteredStudents = students.filter((std: any) => {
    const searchLower = searchTerm.toLowerCase();
    return (
      std.ho_ten.toLowerCase().includes(searchLower) ||
      std.mssv.toLowerCase().includes(searchLower) ||
      std.lop.toLowerCase().includes(searchLower)
    );
  });

  const handleAddSubmit = () => {
    setStudents([{ id: Date.now(), ...newStd }, ...students]);
    setIsAddOpen(false);
  };

  const handleDelete = (id: number) => {
    if (confirm("Xác nhận xóa sinh viên này?")) {
      setStudents(students.filter(s => s.id !== id));
    }
  };

  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Quản lý Sinh viên</h2>
            <p className="text-muted-foreground">
              Quản lý hồ sơ, thẻ thông minh và dữ liệu khuôn mặt phục vụ điểm danh AI.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" /> Thêm Sinh viên
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[700px]">
                <DialogHeader>
                  <DialogTitle>Thêm sinh viên mới</DialogTitle>
                  <DialogDescription>
                    Nhập thông tin cá nhân và upload ảnh để AI học khuôn mặt.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Mã Sinh Viên (MSSV)</Label>
                      <Input placeholder="Ví dụ: 201A030123" />
                    </div>
                    <div className="space-y-2">
                      <Label>Họ và Tên</Label>
                      <Input placeholder="Ví dụ: Nguyễn Văn A" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Email VHU</Label>
                      <Input placeholder="avnguyen@vhu.edu.vn" />
                    </div>
                    <div className="space-y-2">
                      <Label>Số Điện Thoại</Label>
                      <Input placeholder="090..." />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Khoa / Viện</Label>
                      <Input placeholder="Khoa Công nghệ Thông tin" />
                    </div>
                    <div className="space-y-2">
                      <Label>Lớp</Label>
                      <Input placeholder="20CT111" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-lg border border-border mt-2">
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2 text-primary">
                        <Users className="w-4 h-4" /> Người đại diện / Phụ huynh
                      </Label>
                      <Input placeholder="Tên phụ huynh" />
                    </div>
                    <div className="space-y-2">
                      <Label className="flex items-center gap-2 text-primary">
                        <Phone className="w-4 h-4" /> Điện thoại phụ huynh
                      </Label>
                      <Input placeholder="090..." />
                    </div>
                  </div>
                  <div className="space-y-2 border-t pt-4 mt-2">
                    <Label className="flex items-center gap-2">
                      <Upload className="h-4 w-4" />
                      Dữ liệu khuôn mặt (Training Liveness & Face ID)
                    </Label>
                    <div className="grid w-full items-center gap-1.5">
                      <Input type="file" multiple accept="image/*" className="cursor-pointer" />
                      <p className="text-[0.8rem] text-muted-foreground">
                        Nên sử dụng 3-5 hình ảnh góc mặt đa dạng để hệ thống học chính xác nhất.
                      </p>
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button onClick={handleAddSubmit}>Đăng ký & Training AI</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* SEARCH BAR */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-2xl">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm sinh viên theo Tên, MSSV, Lớp hoặc Khoa..."
              className="pl-9 h-11"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Button variant="outline" size="icon">
            <Filter className="h-4 w-4" />
          </Button>
        </div>

        {/* TABLE */}
        <div className="rounded-md border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[300px]">Thông tin Sinh Viên</TableHead>
                <TableHead>MSSV</TableHead>
                <TableHead>Khoa / Lớp</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead>Phụ huynh</TableHead>
                <TableHead className="text-right">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredStudents.map((std: any) => (
                <TableRow key={std.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-10 w-10 border border-border">
                        <AvatarImage
                          src={`https://api.dicebear.com/7.x/notionists/svg?seed=${std.mssv}`}
                        />
                        <AvatarFallback>SV</AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-bold leading-none">
                          {std.ho_ten}
                        </span>
                        <span className="text-xs text-muted-foreground truncate max-w-[150px]">
                          {std.email}
                        </span>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono font-medium text-primary">
                    {std.mssv}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <span className="text-sm font-medium">{std.khoa}</span>
                      <span className="text-xs text-muted-foreground">{std.lop}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={
                        std.trang_thai === "Dang_Hoc"
                          ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                          : std.trang_thai === "Bao_Luu"
                            ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                            : "bg-gray-500/10 text-gray-500 border-gray-500/20"
                      }
                    >
                      {statusMap[std.trang_thai] || std.trang_thai}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <span className="text-sm">{std.nguoi_giam_ho}</span>
                      <span className="text-xs text-muted-foreground font-mono">{std.sdt_giam_ho}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuLabel>Tùy chọn</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => setViewingStd(std)}>
                          <Eye className="mr-2 h-4 w-4" /> <span>Hồ sơ Sinh viên</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setEditingStd(std)}>
                          <Pencil className="mr-2 h-4 w-4" />{" "}
                          <span>Cập nhật</span>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => handleDelete(std.id)}
                          className="text-red-500 focus:text-red-500 focus:bg-red-500/10"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />{" "}
                          <span>Xóa sinh viên</span>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* DIALOG XEM CHI TIẾT */}
      <Dialog open={!!viewingStd} onOpenChange={(open) => !open && setViewingStd(null)}>
        <DialogContent className="sm:max-w-[650px]">
          <DialogHeader>
            <DialogTitle>Hồ Sơ Sinh Viên</DialogTitle>
          </DialogHeader>
          {viewingStd && (
            <div className="grid gap-6 py-4">
              <div className="flex items-center gap-4 border-b pb-6">
                <Avatar className="h-24 w-24 border-4 border-muted">
                  <AvatarImage
                    src={`https://api.dicebear.com/7.x/notionists/svg?seed=${viewingStd.mssv}`}
                  />
                  <AvatarFallback>SV</AvatarFallback>
                </Avatar>
                <div>
                  <h3 className="text-3xl font-bold text-foreground mb-2">
                    {viewingStd.ho_ten}
                  </h3>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-sm px-3 py-1 font-mono">
                      MSSV: {viewingStd.mssv}
                    </Badge>
                    <Badge variant="outline" className={`ml-2 text-sm px-3 py-1 ${viewingStd.trang_thai === "Dang_Hoc"
                        ? "text-emerald-500 border-emerald-500/30"
                        : "text-amber-500 border-amber-500/30"
                      }`}>
                      {statusMap[viewingStd.trang_thai]}
                    </Badge>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <Label className="text-muted-foreground text-xs font-bold uppercase tracking-wider">
                      Thông tin Khoa học
                    </Label>
                    <div className="mt-2 space-y-3 bg-muted/30 p-3 rounded-lg">
                      <div className="flex items-center gap-3 text-sm">
                        <Building2 className="h-4 w-4 text-primary" />
                        <span className="font-medium">{viewingStd.khoa}</span>
                      </div>
                      <div className="flex items-center gap-3 text-sm">
                        <BookOpen className="h-4 w-4 text-primary" />
                        <span>Lớp: {viewingStd.lop}</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <Label className="text-muted-foreground text-xs font-bold uppercase tracking-wider">
                      Liên hệ
                    </Label>
                    <div className="mt-2 space-y-3 bg-muted/30 p-3 rounded-lg">
                      <div className="flex items-center gap-3 text-sm">
                        <Phone className="h-4 w-4 text-primary" />
                        <span className="font-mono">{viewingStd.sdt}</span>
                      </div>
                      <div className="flex items-center gap-3 text-sm">
                        <Mail className="h-4 w-4 text-primary" />
                        <span>{viewingStd.email}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div>
                  <Label className="text-muted-foreground text-xs font-bold uppercase tracking-wider">
                    Thông tin Phụ huynh / Người giám hộ
                  </Label>
                  <div className="mt-2 space-y-3 bg-primary/5 p-4 rounded-lg border border-primary/10">
                    <div className="flex items-center gap-3 text-sm">
                      <User className="h-4 w-4 text-primary" />
                      <span className="font-bold">{viewingStd.nguoi_giam_ho}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <Phone className="h-4 w-4 text-primary" />
                      <span className="font-mono">{viewingStd.sdt_giam_ho}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setViewingStd(null)}>Đóng</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
