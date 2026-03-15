import { useLocation, Link } from "wouter";
import {
  LayoutDashboard,
  Users,
  ClipboardList,
  DoorOpen,
  BarChart3,
  Settings,
  Bell,
  LogOut,
  Menu,
  Search,
  ShieldCheck,
  Camera,
  Brain,
  UserCheck,
  AlertTriangle,
  GraduationCap,
  MapPin,
  History,
  Contact,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

export default function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const navItems = [
    { icon: LayoutDashboard, label: "Tổng quan", href: "/dashboard" },

    {
      icon: DoorOpen,
      label: "Cổng trường & Cửa ra vào",
      href: "/gates",
    },
    {
      icon: MapPin,
      label: "Theo dõi khu vực",
      href: "/tracking",
    },

    {
      icon: ShieldCheck,
      label: "An ninh",
      href: "/security",
    },



    {
      icon: Users,
      label: "Nhân viên trường",
      href: "/staff",
    },
    { icon: Settings, label: "Cài đặt hệ thống", href: "/settings" },
  ];

  const SidebarContent = () => (
    <div className="flex h-full flex-col bg-sidebar border-r border-sidebar-border text-sidebar-foreground">
      {/* Header - Logo & Tên trường */}
      <div className="p-5 flex flex-col items-center justify-center gap-3 border-b border-sidebar-border/50 bg-primary/5">
        <div className="h-16 w-3/4 shrink-0 overflow-hidden shadow-sm rounded-lg border-2 border-white dark:border-slate-800 bg-white flex items-center justify-center relative group">
          <img
            src="https://navigates.vn/wp-content/uploads/2023/03/van-hien.jpg"
            alt="VHU Logo"
            className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105 p-1"
          />
        </div>
        <div className="text-center">
          <h1 className="font-black text-[14px] leading-tight tracking-tight uppercase text-primary">
            Trường Đại Học
            <br />
            Văn Hiến
          </h1>

        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto scrollbar-thin">
        <p className="text-[10px] font-bold uppercase text-muted-foreground/70 px-3 pt-2 pb-1 tracking-widest">
          Quản lý chính
        </p>
        {navItems.slice(0, 4).map((item) => {
          const isActive = location === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <div
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 cursor-pointer group",
                  isActive
                    ? "bg-primary/10 text-primary border-l-2 border-primary pl-[10px]"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:translate-x-1"
                )}
              >
                <item.icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                <span className="truncate">{item.label}</span>
              </div>
            </Link>
          );
        })}

        <p className="text-[10px] font-bold uppercase text-muted-foreground/70 px-3 pt-4 pb-1 tracking-widest">
          Giám sát & An ninh
        </p>
        {navItems.slice(4, 7).map((item) => {
          const isActive = location === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <div
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 cursor-pointer group",
                  isActive
                    ? "bg-primary/10 text-primary border-l-2 border-primary pl-[10px]"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:translate-x-1"
                )}
              >
                <item.icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                <span className="truncate">{item.label}</span>
                {item.href === "/alerts" && (
                  <span className="ml-auto h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                )}
              </div>
            </Link>
          );
        })}

        <p className="text-[10px] font-bold uppercase text-muted-foreground/70 px-3 pt-4 pb-1 tracking-widest">
          Hệ thống
        </p>
        {navItems.slice(7).map((item) => {
          const isActive = location === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <div
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 cursor-pointer group",
                  isActive
                    ? "bg-primary/10 text-primary border-l-2 border-primary pl-[10px]"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:translate-x-1"
                )}
              >
                <item.icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    isActive
                      ? "text-primary"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                <span className="truncate">{item.label}</span>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* System Status */}
      <div className="p-4 border-t border-sidebar-border/50 space-y-2">
        <div className="rounded-lg bg-sidebar-accent/50 p-3 flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <div>
            <p className="text-xs font-medium">Trạng thái hệ thống</p>
            <p className="text-[10px] text-emerald-500 font-mono">
              ĐANG GIÁM SÁT
            </p>
          </div>
        </div>
        <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-3 flex items-center gap-3">
          <Camera className="h-4 w-4 text-blue-500" />
          <div>
            <p className="text-xs font-medium">Camera hoạt động</p>
            <p className="text-[10px] text-blue-500 font-mono">
              12/12 ONLINE
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background flex">
      {/* Desktop Sidebar */}
      <div className="hidden md:block w-[270px] shrink-0 h-screen sticky top-0">
        <SidebarContent />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b bg-card/50 backdrop-blur-sm sticky top-0 z-30 px-4 md:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent
                side="left"
                className="p-0 w-[270px] border-r border-sidebar-border bg-sidebar"
              >
                <SidebarContent />
              </SheetContent>
            </Sheet>

            <div className="hidden md:flex items-center relative w-full lg:w-[600px]">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Tìm thông tin sinh viên, camera, sự kiện, biển số xe..."
                className="pl-9 bg-muted/50 border-none focus-visible:ring-1 w-full h-10 text-sm shadow-inner"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Nút cảnh báo khẩn cấp */}



            {/* Notification Bell */}
            <Button
              variant="ghost"
              size="icon"
              className="relative text-muted-foreground hover:text-foreground"
            >
              <Bell className="h-5 w-5" />
              <span className="absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full bg-destructive border-2 border-background"></span>
            </Button>

            {/* User Menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className="relative h-9 w-9 rounded-full"
                >
                  <Avatar className="h-9 w-9 border border-border">
                    <AvatarImage
                      src="https://github.com/shadcn.png"
                      alt="Admin"
                    />
                    <AvatarFallback>QT</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" forceMount>
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium leading-none">
                      Quản trị viên
                    </p>
                    <p className="text-xs leading-none text-muted-foreground">
                      admin@truonghoc.edu.vn
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Hồ sơ cá nhân</DropdownMenuItem>
                <DropdownMenuItem>Cài đặt tài khoản</DropdownMenuItem>
                <DropdownMenuItem>Nhật ký hoạt động</DropdownMenuItem>
                <DropdownMenuSeparator />
                <Link href="/auth">
                  <DropdownMenuItem className="text-destructive focus:text-destructive cursor-pointer">
                    <LogOut className="mr-2 h-4 w-4" />
                    Đăng xuất
                  </DropdownMenuItem>
                </Link>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-8 overflow-y-auto">
          <div className="mx-auto max-w-7xl space-y-8 animate-in fade-in duration-500 slide-in-from-bottom-4">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}