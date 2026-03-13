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
  FileSpreadsheet,
  Filter,
  MoreHorizontal,
  Eye,
  Pencil,
  Lock,
  Save,
  User,
  Phone,
  MapPin,
  Calendar,
  Building2,
  Trash2,
  Upload, // Thêm icon Upload
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
import { useEffect, useState } from "react";
import { api } from "../../../service/api";
import * as XLSX from "xlsx";
import * as FileSaver from "file-saver";

const statusMap: Record<string, string> = {
  Dang_Lam: "Đang làm",
  Nghi_Phep: "Nghỉ phép",
  Da_Nghi: "Đã nghỉ",
};

export default function Employees() {
  const [employees, setEmployees] = useState([]);
  const [editingEmp, setEditingEmp] = useState<any>(null);
  const [viewingEmp, setViewingEmp] = useState<any>(null);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  // --- STATE CHO FORM THÊM MỚI ---
  const [newEmp, setNewEmp] = useState<any>({
    ho_ten: "",
    email: "",
    sdt: "",
    dia_chi: "",
    ten_phong: "",
    ten_chuc_vu: "",
    trang_thai: "Dang_Lam",
  });

  // --- STATE MỚI: LƯU FILE ẢNH KHUÔN MẶT ---
  const [faceFiles, setFaceFiles] = useState<FileList | null>(null);

  const fetchUsers = async () => {
    const res = await api.getUsers();
    // Xử lý trường hợp API trả về mảng trực tiếp hoặc object chứa data
    setEmployees(Array.isArray(res) ? res : res.data || []);
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  // --- LOGIC XUẤT EXCEL (GIỮ NGUYÊN) ---
  const handleExportExcel = () => {
    const excelData = filteredEmployees.map((emp: any) => ({
      "Mã Nhân Viên": `NV${String(emp.ma_nv).padStart(3, "0")}`,
      "Họ và Tên": emp.ho_ten,
      Email: emp.email,
      "Số điện thoại": emp.sdt || "",
      "Phòng ban": emp.ten_phong || "Chưa xếp",
      "Chức vụ": emp.ten_chuc_vu || "Nhân viên",
      "Trạng thái": statusMap[emp.trang_thai] || emp.trang_thai,
      "Địa chỉ": emp.dia_chi || "",
    }));
    const worksheet = XLSX.utils.json_to_sheet(excelData);
    worksheet["!cols"] = [
      { wch: 15 },
      { wch: 25 },
      { wch: 30 },
      { wch: 15 },
      { wch: 20 },
      { wch: 20 },
      { wch: 15 },
      { wch: 30 },
    ];
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Danh sách nhân viên");
    const excelBuffer = XLSX.write(workbook, {
      bookType: "xlsx",
      type: "array",
    });
    const data = new Blob([excelBuffer], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;charset=UTF-8",
    });
    FileSaver.saveAs(
      data,
      `Danh_Sach_Nhan_Vien_${new Date().toISOString().slice(0, 10)}.xlsx`
    );
  };

  const filteredEmployees = employees.filter((emp: any) => {
    const searchLower = searchTerm.toLowerCase();
    return (
      (emp.ho_ten && emp.ho_ten.toLowerCase().includes(searchLower)) ||
      (emp.email && emp.email.toLowerCase().includes(searchLower)) ||
      String(emp.ma_nv).includes(searchLower) ||
      (emp.ten_phong && emp.ten_phong.toLowerCase().includes(searchLower))
    );
  });

  // --- LOGIC FORM THÊM MỚI (ĐÃ CẬP NHẬT ĐỂ GỬI ẢNH) ---
  const handleAddChange = (e: any) => {
    const { id, value } = e.target;
    setNewEmp((prev: any) => ({ ...prev, [id]: value }));
  };

  // Hàm xử lý khi chọn file
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFaceFiles(e.target.files);
    }
  };

  const handleAddSubmit = async () => {
    if (!newEmp.ho_ten || !newEmp.email) {
      alert("Vui lòng nhập Tên và Email!");
      return;
    }

    // 1. Tạo FormData để chứa cả text và file
    const formData = new FormData();

    // Thêm các trường text
    Object.keys(newEmp).forEach((key) => {
      formData.append(key, newEmp[key]);
    });

    // Thêm các file ảnh (nếu có)
    if (faceFiles) {
      for (let i = 0; i < faceFiles.length; i++) {
        formData.append("faces", faceFiles[i]);
      }
    }

    try {
      // 2. Gọi API Python trực tiếp (hoặc qua service nếu muốn)
      // Lưu ý: Port 5000 là port của server Flask Python
      const res = await fetch(
        "http://127.0.0.1:5000/api/add_employee_with_faces",
        {
          method: "POST",
          body: formData,
          // Không set Content-Type header thủ công, để browser tự set boundary
        }
      );

      const data = await res.json();

      if (data.success) {
        alert("✅ " + data.message);
        setIsAddOpen(false);
        // Reset form
        setNewEmp({
          ho_ten: "",
          email: "",
          sdt: "",
          dia_chi: "",
          ten_phong: "",
          ten_chuc_vu: "",
          trang_thai: "Dang_Lam",
        });
        setFaceFiles(null);
        fetchUsers(); // Tải lại danh sách
      } else {
        alert("❌ Lỗi: " + data.message);
      }
    } catch (error) {
      console.error("Lỗi thêm nhân viên:", error);
      alert("Lỗi kết nối đến server!");
    }
  };

  // --- CÁC LOGIC KHÁC GIỮ NGUYÊN ---
  const handleEdit = (emp: any) => setEditingEmp({ ...emp });
  const handleEditChange = (e: any) => {
    const { id, value } = e.target;
    setEditingEmp((prev: any) => ({ ...prev, [id]: value }));
  };
  const handleSaveEdit = async () => {
    if (!editingEmp) return;
    const res = await api.updateUser(editingEmp);
    if (res.success) {
      alert("Cập nhật thành công!");
      setEditingEmp(null);
      fetchUsers();
    } else {
      alert("Lỗi: " + res.message);
    }
  };

  const handleDelete = async (emp: any) => {
    if (
      confirm(
        `CẢNH BÁO: Bạn có chắc muốn XÓA VĨNH VIỄN nhân viên: ${emp.ho_ten}?`
      )
    ) {
      const res = await api.deleteUser(emp.ma_nv);
      if (res.success) {
        alert("Đã xóa nhân viên.");
        fetchUsers();
      } else {
        alert("Lỗi xóa: " + res.message);
      }
    }
  };

  const handleViewDetail = (emp: any) => setViewingEmp(emp);
  const handleLock = (emp: any) => {
    if (confirm(`Khóa tài khoản ${emp.ho_ten}?`))
      console.log("Đã khóa:", emp.ma_nv);
  };

  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              Danh sách nhân viên
            </h2>
            <p className="text-muted-foreground">
              Quản lý hồ sơ nhân sự và dữ liệu khuôn mặt.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleExportExcel}>
              <FileSpreadsheet className="mr-2 h-4 w-4" /> Xuất Excel
            </Button>

            {/* --- DIALOG THÊM MỚI --- */}
            <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" /> Thêm mới
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                  <DialogTitle>Thêm nhân viên & Khuôn mặt</DialogTitle>
                  <DialogDescription>
                    Nhập thông tin và tải ảnh lên để training AI.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {/* Cột 1: Thông tin cơ bản */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ho_ten">
                        Họ tên <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        id="ho_ten"
                        value={newEmp.ho_ten}
                        onChange={handleAddChange}
                        placeholder="Nguyễn Văn A"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">
                        Email <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        id="email"
                        value={newEmp.email}
                        onChange={handleAddChange}
                        placeholder="abc@company.com"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="sdt">Số điện thoại</Label>
                      <Input
                        id="sdt"
                        value={newEmp.sdt}
                        onChange={handleAddChange}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="dia_chi">Địa chỉ</Label>
                      <Input
                        id="dia_chi"
                        value={newEmp.dia_chi}
                        onChange={handleAddChange}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="ten_phong">Phòng ban</Label>
                      <Input
                        id="ten_phong"
                        value={newEmp.ten_phong}
                        onChange={handleAddChange}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="ten_chuc_vu">Chức vụ</Label>
                      <Input
                        id="ten_chuc_vu"
                        value={newEmp.ten_chuc_vu}
                        onChange={handleAddChange}
                      />
                    </div>
                  </div>

                  {/* --- PHẦN UPLOAD ẢNH MỚI THÊM VÀO --- */}
                  <div className="space-y-2 border-t pt-4 mt-2">
                    <Label className="flex items-center gap-2">
                      <Upload className="h-4 w-4" />
                      Ảnh khuôn mặt (Training AI)
                    </Label>
                    <div className="grid w-full max-w-sm items-center gap-1.5">
                      <Input
                        id="faces"
                        type="file"
                        multiple
                        accept="image/*"
                        onChange={handleFileChange}
                        className="cursor-pointer"
                      />
                      <p className="text-[0.8rem] text-muted-foreground">
                        Chọn nhiều ảnh rõ mặt. Hệ thống sẽ tự động trích xuất
                        vector.
                      </p>
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button onClick={handleAddSubmit}>Lưu & Training</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* SEARCH BAR */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm theo tên, mã NV, phòng ban..."
              className="pl-9"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Button variant="outline" size="icon">
            <Filter className="h-4 w-4" />
          </Button>
        </div>

        {/* TABLE HIỂN THỊ */}
        <div className="rounded-md border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[300px]">Thông tin nhân viên</TableHead>
                <TableHead>Mã NV</TableHead>
                <TableHead>Phòng ban</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead>Chức vụ</TableHead>
                <TableHead className="text-right">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEmployees.map((emp: any) => (
                <TableRow key={emp.ma_nv}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-10 w-10 border border-gray-500">
                        <AvatarImage
                          src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${emp.ma_nv}`}
                        />
                        <AvatarFallback>NV</AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-bold text-white leading-none">
                          {emp.ho_ten}
                        </span>
                        <span className="text-xs text-gray-300 truncate max-w-[150px]">
                          {emp.email}
                        </span>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    NV{String(emp.ma_nv).padStart(3, "0")}
                  </TableCell>
                  <TableCell>{emp.ten_phong || "—"}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={
                        emp.trang_thai === "Dang_Lam"
                          ? "bg-emerald-500/10 text-emerald-500"
                          : "bg-gray-500/10 text-gray-400"
                      }
                    >
                      {statusMap[emp.trang_thai] || emp.trang_thai}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {emp.ten_chuc_vu || "Nhân viên"}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-white hover:bg-gray-800"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuLabel>Hành động</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => handleViewDetail(emp)}>
                          <Eye className="mr-2 h-4 w-4" /> <span>Chi tiết</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleEdit(emp)}>
                          <Pencil className="mr-2 h-4 w-4" />{" "}
                          <span>Sửa hồ sơ</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleLock(emp)}>
                          <Lock className="mr-2 h-4 w-4" />{" "}
                          <span>Khóa tài khoản</span>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => handleDelete(emp)}
                          className="text-red-500 focus:text-red-500 focus:bg-red-500/10"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />{" "}
                          <span>Xóa nhân viên</span>
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

      {/* DIALOG XEM CHI TIẾT (GIỮ NGUYÊN) */}
      <Dialog
        open={!!viewingEmp}
        onOpenChange={(open) => !open && setViewingEmp(null)}
      >
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Hồ sơ chi tiết</DialogTitle>
          </DialogHeader>
          {viewingEmp && (
            <div className="grid gap-6 py-4">
              <div className="flex items-center gap-4 border-b pb-4">
                <Avatar className="h-20 w-20 border-2 border-gray-200">
                  <AvatarImage
                    src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${viewingEmp.ma_nv}`}
                  />
                  <AvatarFallback>NV</AvatarFallback>
                </Avatar>
                <div>
                  <h3 className="text-2xl font-bold text-foreground">
                    {viewingEmp.ho_ten}
                  </h3>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="secondary">
                      {viewingEmp.ten_chuc_vu || "Nhân viên"}
                    </Badge>
                    <Badge variant="outline" className="ml-2">
                      {statusMap[viewingEmp.trang_thai] ||
                        viewingEmp.trang_thai}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    Mã NV: NV{String(viewingEmp.ma_nv).padStart(3, "0")}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-muted-foreground text-xs uppercase">
                    Email
                  </Label>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <User className="h-4 w-4 text-gray-500" />{" "}
                    {viewingEmp.email || "---"}
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-muted-foreground text-xs uppercase">
                    SĐT
                  </Label>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Phone className="h-4 w-4 text-gray-500" />{" "}
                    {viewingEmp.sdt || "---"}
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-muted-foreground text-xs uppercase">
                    Phòng ban
                  </Label>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Building2 className="h-4 w-4 text-gray-500" />{" "}
                    {viewingEmp.ten_phong || "---"}
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-muted-foreground text-xs uppercase">
                    Ngày sinh
                  </Label>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Calendar className="h-4 w-4 text-gray-500" />{" "}
                    {viewingEmp.ngay_sinh || "---"}
                  </div>
                </div>
                <div className="space-y-1 col-span-2">
                  <Label className="text-muted-foreground text-xs uppercase">
                    Địa chỉ
                  </Label>
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <MapPin className="h-4 w-4 text-gray-500" />{" "}
                    {viewingEmp.dia_chi || "---"}
                  </div>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setViewingEmp(null)}>Đóng</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* DIALOG SỬA (GIỮ NGUYÊN) */}
      <Dialog
        open={!!editingEmp}
        onOpenChange={(open) => !open && setEditingEmp(null)}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Cập nhật hồ sơ</DialogTitle>
          </DialogHeader>
          {editingEmp && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="ho_ten" className="text-right">
                  Họ tên
                </Label>
                <Input
                  id="ho_ten"
                  value={editingEmp.ho_ten || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="email" className="text-right">
                  Email
                </Label>
                <Input
                  id="email"
                  value={editingEmp.email || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="sdt" className="text-right">
                  Số ĐT
                </Label>
                <Input
                  id="sdt"
                  value={editingEmp.sdt || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="dia_chi" className="text-right">
                  Địa chỉ
                </Label>
                <Input
                  id="dia_chi"
                  value={editingEmp.dia_chi || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="ten_phong" className="text-right">
                  Phòng ban
                </Label>
                <Input
                  id="ten_phong"
                  value={editingEmp.ten_phong || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="ten_chuc_vu" className="text-right">
                  Chức vụ
                </Label>
                <Input
                  id="ten_chuc_vu"
                  value={editingEmp.ten_chuc_vu || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="trang_thai" className="text-right">
                  Trạng thái
                </Label>
                <Input
                  id="trang_thai"
                  value={editingEmp.trang_thai || ""}
                  onChange={handleEditChange}
                  className="col-span-3"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button onClick={handleSaveEdit}>
              <Save className="mr-2 h-4 w-4" /> Lưu thay đổi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
