import Layout from "@/components/Layout";

export default function Guardians() {
  return (
    <Layout>
      <div className="flex flex-col gap-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Phụ huynh & Người đón</h2>
          <p className="text-muted-foreground">Quản lý danh sách phụ huynh và người được ủy quyền đón học sinh</p>
        </div>
        
        <div className="flex items-center justify-center h-64 border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
          <p className="text-slate-500 font-medium">Chức năng quản lý phụ huynh đang được phát triển...</p>
        </div>
      </div>
    </Layout>
  );
}
