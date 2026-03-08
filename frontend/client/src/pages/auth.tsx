import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLocation } from "wouter";
import {
  ShieldCheck,
  Eye,
  EyeOff,
  Lock,
  Loader2,
  ServerCog,
} from "lucide-react"; // Thêm icon ServerCog cho ngầu
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
// Giả sử anh có toast để báo lỗi
import { api } from "../../../service/api";

const loginSchema = z.object({
  username: z.string().min(1, "Vui lòng nhập Mã nhân viên hoặc Email"),
  password: z.string().min(1, "Vui lòng nhập mật khẩu xác thực"),
  rememberMe: z.boolean().default(false),
});

export default function AuthPage() {
  const [, setLocation] = useLocation();
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "", // Thực tế thì nên để trống
      password: "",
      rememberMe: false,
    },
  });

  async function onSubmit(values: z.infer<typeof loginSchema>) {
    setIsLoading(true);
    try {
      const cleanUsername = values.username.includes("@")
        ? values.username.split("@")[0]
        : values.username;

      const response = await api.login(cleanUsername, values.password);

      if (response.success) {
        localStorage.setItem("user_role", response.user.role);
        localStorage.setItem("user_dept", response.user.dept);
        setLocation("/dashboard");
      }
    } catch (error: any) {
      form.setError("root", {
        message: "Thông tin xác thực không chính xác. Vui lòng kiểm tra lại.",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background relative overflow-hidden">
      {/* Background Texture giữ nguyên */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_50%,#000_70%,transparent_100%)]" />

      <Card className="w-full max-w-md border-muted shadow-2xl relative z-10 bg-card/95 backdrop-blur-sm">
        <CardHeader className="space-y-2 text-center pb-8">
          <div className="flex justify-center mb-2">
            <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-[0_0_30px_rgba(16,185,129,0.15)]">
              <ShieldCheck className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight uppercase">
            Security Operation Center
          </CardTitle>
          <CardDescription className="text-base">
            Hệ thống Quản lý An ninh & Giám sát Tập trung
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tài khoản quản trị (ID / Email)</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Ví dụ: NV-2025 hoặc admin@hethong.vn"
                        {...field}
                        className="bg-muted/30 h-11"
                        disabled={isLoading}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mật khẩu xác thực</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Input
                          type={showPassword ? "text" : "password"}
                          placeholder="Nhập mật khẩu cấp phát..."
                          {...field}
                          className="bg-muted/30 pr-10 h-11"
                          disabled={isLoading}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="absolute right-0 top-0 h-full px-3 hover:bg-transparent text-muted-foreground hover:text-foreground"
                          onClick={() => setShowPassword(!showPassword)}
                          disabled={isLoading}
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="flex items-center justify-between pt-1">
                <FormField
                  control={form.control}
                  name="rememberMe"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center space-x-2 space-y-0">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                          className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                        />
                      </FormControl>
                      <div className="space-y-1 leading-none">
                        <FormLabel className="text-sm font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
                          Duy trì đăng nhập
                        </FormLabel>
                      </div>
                    </FormItem>
                  )}
                />
                <Button
                  variant="link"
                  className="px-0 font-normal text-sm text-primary hover:text-primary/80"
                  type="button"
                >
                  Quên mật khẩu?
                </Button>
              </div>

              {form.formState.errors.root && (
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm text-center font-medium">
                  {form.formState.errors.root.message}
                </div>
              )}

              <Button
                type="submit"
                className="w-full h-11 font-bold shadow-[0_4px_14px_0_rgba(16,185,129,0.39)] hover:shadow-[0_6px_20px_rgba(16,185,129,0.23)] hover:-translate-y-0.5 transition-all duration-200"
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Lock className="mr-2 h-4 w-4" />
                )}
                {isLoading
                  ? "Đang xác thực thông tin..."
                  : "ĐĂNG NHẬP HỆ THỐNG"}
              </Button>
            </form>
          </Form>
        </CardContent>
        <CardFooter className="flex flex-col gap-2 justify-center border-t bg-muted/20 py-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ServerCog className="h-3 w-3" />
            <span>Phiên bản v2.4.0 (Stable)</span>
          </div>
          <p className="text-[10px] text-muted-foreground/60 text-center uppercase tracking-wider">
            © 2025 VN-SmartTech Security Solutions. <br />
            Mọi truy cập trái phép đều bị ghi lại.
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
