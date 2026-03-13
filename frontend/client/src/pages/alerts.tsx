import Layout from "@/components/Layout";

export default function Alerts() {
  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Cảnh báo bất thường</h2>
          <p className="text-muted-foreground">Hệ thống ghi nhận và báo cáo các sự kiện an ninh bất thường</p>
        </div>
        
        <div className="flex items-center justify-center h-64 border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
          <p className="text-slate-500 font-medium">Chức năng cảnh báo bất thường đang được phát triển...</p>
        </div>
      </div>
    </Layout>
  );
}
