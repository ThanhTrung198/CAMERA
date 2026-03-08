import Layout from "@/components/Layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Bell, Shield, Camera, User } from "lucide-react";

export default function Settings() {
  return (
    <Layout>
      <div className="flex flex-col gap-8 max-w-4xl">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Cài đặt Hệ thống</h2>
          <p className="text-muted-foreground">Cấu hình thông số cơ sở và tùy chọn</p>
        </div>

        <Tabs defaultValue="general" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="general">Chung</TabsTrigger>
            <TabsTrigger value="security">An ninh</TabsTrigger>
            <TabsTrigger value="notifications">Thông báo</TabsTrigger>
            <TabsTrigger value="cameras">Camera</TabsTrigger>
          </TabsList>
          
          <TabsContent value="general" className="mt-6 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Thông tin Cơ sở</CardTitle>
                <CardDescription>Chi tiết cơ bản về cài đặt này</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>Tên Cơ sở</Label>
                  <Input defaultValue="Trụ sở chính - Tòa nhà A" />
                </div>
                <div className="grid gap-2">
                  <Label>Liên hệ Quản trị</Label>
                  <Input defaultValue="admin@secureos.com" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Tùy chọn Hệ thống</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Chế độ Tối</Label>
                    <p className="text-sm text-muted-foreground">Bắt buộc chế độ tối cho tất cả thiết bị đầu cuối</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Tự động Đăng xuất</Label>
                    <p className="text-sm text-muted-foreground">Khóa phiên sau 15 phút không hoạt động</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="security" className="mt-6 space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-primary" />
                  <CardTitle>Giao thức Kiểm soát Truy cập</CardTitle>
                </div>
                <CardDescription>Chính sách an ninh toàn cầu</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-destructive font-bold">Chế độ Phong tỏa</Label>
                    <p className="text-sm text-muted-foreground">Niêm phong tất cả cửa và vô hiệu hóa thẻ truy cập</p>
                  </div>
                  <Switch />
                </div>
                 <Separator />
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Xác thực 2 Yếu tố</Label>
                    <p className="text-sm text-muted-foreground">Yêu cầu sinh trắc học + mã PIN cho phòng máy chủ</p>
                  </div>
                  <Switch defaultChecked />
                </div>
                 <Separator />
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Sàng lọc Khách</Label>
                    <p className="text-sm text-muted-foreground">Bắt buộc phê duyệt thủ công cho thẻ khách</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

           <TabsContent value="notifications" className="mt-6">
             <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Bell className="h-5 w-5 text-primary" />
                  <CardTitle>Cấu hình Cảnh báo</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                 <div className="grid gap-2">
                  <Label>Người nhận Email</Label>
                  <Input defaultValue="security-team@secureos.com" />
                </div>
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Thông báo Đẩy</Label>
                    <p className="text-sm text-muted-foreground">Gửi cảnh báo di động cho các sự kiện quan trọng</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </CardContent>
             </Card>
           </TabsContent>
           
           <TabsContent value="cameras" className="mt-6">
             <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Camera className="h-5 w-5 text-primary" />
                    <CardTitle>Nguồn Vào & Luồng RTSP</CardTitle>
                  </div>
                  <Button size="sm">
                    <Camera className="mr-2 h-4 w-4" />
                    Thêm Camera
                  </Button>
                </div>
                <CardDescription>Quản lý kết nối camera IP và cấu hình luồng.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="rounded-md border">
                  <div className="grid grid-cols-5 gap-4 p-4 border-b bg-muted/50 text-sm font-medium">
                    <div className="col-span-2">Tên Camera</div>
                    <div>Loại</div>
                    <div>Trạng thái</div>
                    <div className="text-right">Hành động</div>
                  </div>
                  <div className="p-4 flex items-center justify-between hover:bg-muted/20 transition-colors">
                    <div className="col-span-2 grid grid-cols-2 gap-4 w-[40%]">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                          <Camera className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="font-medium">CAM-01 Cổng vào</div>
                          <div className="text-xs text-muted-foreground font-mono">192.168.1.101:554</div>
                        </div>
                      </div>
                    </div>
                    <div className="w-[20%]">
                      <Badge variant="outline">RTSP / H.264</Badge>
                    </div>
                    <div className="w-[20%]">
                      <div className="flex items-center gap-2 text-emerald-500 text-sm">
                        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        Trực tuyến (24fps)
                      </div>
                    </div>
                    <div className="w-[20%] text-right">
                      <Button variant="ghost" size="sm">Cấu hình</Button>
                    </div>
                  </div>
                  <div className="p-4 flex items-center justify-between hover:bg-muted/20 transition-colors border-t">
                     <div className="col-span-2 grid grid-cols-2 gap-4 w-[40%]">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                          <Camera className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="font-medium">CAM-02 Hành lang</div>
                          <div className="text-xs text-muted-foreground font-mono">192.168.1.102:554</div>
                        </div>
                      </div>
                    </div>
                    <div className="w-[20%]">
                      <Badge variant="outline">RTSP / H.265</Badge>
                    </div>
                    <div className="w-[20%]">
                      <div className="flex items-center gap-2 text-emerald-500 text-sm">
                        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        Trực tuyến (30fps)
                      </div>
                    </div>
                    <div className="w-[20%] text-right">
                      <Button variant="ghost" size="sm">Cấu hình</Button>
                    </div>
                  </div>
                   <div className="p-4 flex items-center justify-between hover:bg-muted/20 transition-colors border-t">
                     <div className="col-span-2 grid grid-cols-2 gap-4 w-[40%]">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                          <Camera className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="font-medium">CAM-03 Phòng máy chủ</div>
                          <div className="text-xs text-muted-foreground font-mono">192.168.1.103:554</div>
                        </div>
                      </div>
                    </div>
                    <div className="w-[20%]">
                      <Badge variant="outline">Webcam / USB</Badge>
                    </div>
                    <div className="w-[20%]">
                      <div className="flex items-center gap-2 text-amber-500 text-sm">
                        <div className="h-2 w-2 rounded-full bg-amber-500" />
                        Đang kết nối...
                      </div>
                    </div>
                    <div className="w-[20%] text-right">
                      <Button variant="ghost" size="sm">Cấu hình</Button>
                    </div>
                  </div>
                </div>
                
                <div className="border rounded-lg p-4 bg-muted/10">
                  <h4 className="font-medium mb-4">Thêm Luồng Mới</h4>
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="grid gap-2">
                      <Label>Tên Camera</Label>
                      <Input placeholder="ví dụ: Cổng chính" />
                    </div>
                    <div className="grid gap-2">
                      <Label>URL Luồng (RTSP/HTTP)</Label>
                      <Input placeholder="rtsp://admin:pass@192.168.1.x:554/stream1" />
                    </div>
                    <div className="grid gap-2">
                      <Label>&nbsp;</Label>
                      <Button variant="secondary" className="w-full">Kiểm tra Kết nối</Button>
                    </div>
                  </div>
                </div>
              </CardContent>
             </Card>
           </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}