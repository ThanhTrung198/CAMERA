import Layout from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Search,
    Database,
    Brain,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    ChevronDown,
    ChevronRight,
    RefreshCw,
    Binary,
} from "lucide-react";
import { useEffect, useState } from "react";

const BASE_URL = "http://127.0.0.1:5000";

interface VectorInfo {
    embedding_id: number | string;
    dim: number;
    norm: number;
    is_normalized: boolean;
    preview: number[];
    stats: {
        min: number;
        max: number;
        mean: number;
        std: number;
    };
}

interface Employee {
    ma_nv: number;
    ho_ten: string;
    email: string;
    ten_phong: string;
    ten_chuc_vu: string;
    trang_thai: string;
    vectors: VectorInfo[];
    vector_count: number;
    has_face_data: boolean;
    intra_similarity: {
        min: number;
        max: number;
        avg: number;
    } | null;
}

interface Summary {
    total_employees: number;
    with_face_data: number;
    without_face_data: number;
    total_vectors: number;
    avg_vectors_per_person: number;
}

export default function TrainingData() {
    const [employees, setEmployees] = useState<Employee[]>([]);
    const [summary, setSummary] = useState<Summary | null>(null);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [selectedVector, setSelectedVector] = useState<VectorInfo | null>(null);
    const [filter, setFilter] = useState<"all" | "with" | "without">("all");

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${BASE_URL}/api/training-data`);
            const data = await res.json();
            if (data.success) {
                setEmployees(data.employees || []);
                setSummary(data.summary || null);
            }
        } catch (error) {
            console.error("Error fetching training data:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const filtered = employees.filter((emp) => {
        const matchSearch =
            emp.ho_ten?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            emp.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            String(emp.ma_nv).includes(searchTerm);

        if (filter === "with") return matchSearch && emp.has_face_data;
        if (filter === "without") return matchSearch && !emp.has_face_data;
        return matchSearch;
    });

    const getQualityBadge = (emp: Employee) => {
        if (!emp.has_face_data)
            return (
                <Badge variant="destructive" className="gap-1">
                    <XCircle className="h-3 w-3" /> Chưa training
                </Badge>
            );
        if (emp.vector_count < 3)
            return (
                <Badge
                    variant="outline"
                    className="gap-1 bg-amber-500/10 text-amber-500 border-amber-500/30"
                >
                    <AlertTriangle className="h-3 w-3" /> Ít dữ liệu
                </Badge>
            );
        return (
            <Badge
                variant="outline"
                className="gap-1 bg-emerald-500/10 text-emerald-500 border-emerald-500/30"
            >
                <CheckCircle2 className="h-3 w-3" /> Đủ dữ liệu
            </Badge>
        );
    };

    const getSimilarityColor = (sim: number) => {
        if (sim >= 0.9) return "text-emerald-400";
        if (sim >= 0.7) return "text-amber-400";
        return "text-red-400";
    };

    return (
        <Layout>
            <div className="flex flex-col gap-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-3xl font-bold tracking-tight flex items-center gap-2">
                            <Brain className="h-8 w-8 text-primary" />
                            Dữ liệu Training
                        </h2>
                        <p className="text-muted-foreground">
                            Xem vector, metadata khuôn mặt — trước & sau khi training AI nhận
                            diện.
                        </p>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={fetchData}
                        disabled={loading}
                    >
                        <RefreshCw
                            className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
                        />
                        Tải lại
                    </Button>
                </div>

                {/* Summary Cards */}
                {summary && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="rounded-lg border bg-card p-4 space-y-1">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                Tổng nhân viên
                            </p>
                            <p className="text-2xl font-bold">{summary.total_employees}</p>
                        </div>
                        <div className="rounded-lg border bg-card p-4 space-y-1">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                Có dữ liệu mặt
                            </p>
                            <p className="text-2xl font-bold text-emerald-500">
                                {summary.with_face_data}
                            </p>
                        </div>
                        <div className="rounded-lg border bg-card p-4 space-y-1">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                Chưa có dữ liệu
                            </p>
                            <p className="text-2xl font-bold text-red-500">
                                {summary.without_face_data}
                            </p>
                        </div>
                        <div className="rounded-lg border bg-card p-4 space-y-1">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                Tổng vectors
                            </p>
                            <p className="text-2xl font-bold text-blue-500">
                                {summary.total_vectors}
                            </p>
                        </div>
                        <div className="rounded-lg border bg-card p-4 space-y-1">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                TB vector/người
                            </p>
                            <p className="text-2xl font-bold">
                                {summary.avg_vectors_per_person}
                            </p>
                        </div>
                    </div>
                )}

                {/* Filter + Search */}
                <div className="flex items-center gap-3">
                    <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Tìm theo tên, mã NV..."
                            className="pl-9"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                    <div className="flex gap-1">
                        {(["all", "with", "without"] as const).map((f) => (
                            <Button
                                key={f}
                                variant={filter === f ? "default" : "outline"}
                                size="sm"
                                onClick={() => setFilter(f)}
                            >
                                {f === "all" && "Tất cả"}
                                {f === "with" && "Có dữ liệu"}
                                {f === "without" && "Thiếu dữ liệu"}
                            </Button>
                        ))}
                    </div>
                </div>

                {/* Main Table */}
                <div className="rounded-md border bg-card">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-10"></TableHead>
                                <TableHead className="w-[250px]">Nhân viên</TableHead>
                                <TableHead>Phòng ban</TableHead>
                                <TableHead>Trạng thái training</TableHead>
                                <TableHead className="text-center">Vectors</TableHead>
                                <TableHead className="text-center">Chiều (Dim)</TableHead>
                                <TableHead className="text-center">Similarity</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {loading ? (
                                <TableRow>
                                    <TableCell colSpan={7} className="text-center py-12">
                                        <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-muted-foreground" />
                                        <p className="text-muted-foreground">Đang tải dữ liệu...</p>
                                    </TableCell>
                                </TableRow>
                            ) : filtered.length === 0 ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={7}
                                        className="text-center py-12 text-muted-foreground"
                                    >
                                        Không tìm thấy nhân viên nào.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filtered.map((emp) => (
                                    <>
                                        <TableRow
                                            key={emp.ma_nv}
                                            className="cursor-pointer hover:bg-muted/50"
                                            onClick={() =>
                                                setExpandedId(
                                                    expandedId === emp.ma_nv ? null : emp.ma_nv
                                                )
                                            }
                                        >
                                            <TableCell>
                                                {expandedId === emp.ma_nv ? (
                                                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                                ) : (
                                                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <div>
                                                    <span className="font-medium">{emp.ho_ten}</span>
                                                    <p className="text-xs text-muted-foreground">
                                                        NV{String(emp.ma_nv).padStart(3, "0")} •{" "}
                                                        {emp.email}
                                                    </p>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-muted-foreground">
                                                {emp.ten_phong}
                                            </TableCell>
                                            <TableCell>{getQualityBadge(emp)}</TableCell>
                                            <TableCell className="text-center">
                                                <span
                                                    className={`font-mono font-bold ${emp.vector_count === 0
                                                            ? "text-red-500"
                                                            : emp.vector_count < 3
                                                                ? "text-amber-500"
                                                                : "text-emerald-500"
                                                        }`}
                                                >
                                                    {emp.vector_count}
                                                </span>
                                            </TableCell>
                                            <TableCell className="text-center font-mono text-xs text-muted-foreground">
                                                {emp.vectors[0]?.dim || "—"}
                                            </TableCell>
                                            <TableCell className="text-center">
                                                {emp.intra_similarity ? (
                                                    <span
                                                        className={`font-mono text-sm font-bold ${getSimilarityColor(
                                                            emp.intra_similarity.avg
                                                        )}`}
                                                    >
                                                        {emp.intra_similarity.avg.toFixed(3)}
                                                    </span>
                                                ) : (
                                                    <span className="text-muted-foreground text-xs">
                                                        —
                                                    </span>
                                                )}
                                            </TableCell>
                                        </TableRow>

                                        {/* Expanded Detail */}
                                        {expandedId === emp.ma_nv && (
                                            <TableRow key={`${emp.ma_nv}-detail`}>
                                                <TableCell colSpan={7} className="bg-muted/30 p-0">
                                                    <div className="p-4 space-y-4">
                                                        {/* Info Cards */}
                                                        <div className="grid grid-cols-3 gap-3">
                                                            <div className="rounded-lg border bg-card/50 p-3">
                                                                <p className="text-xs text-muted-foreground mb-1">
                                                                    Thông tin
                                                                </p>
                                                                <p className="text-sm">
                                                                    <span className="text-muted-foreground">
                                                                        Chức vụ:
                                                                    </span>{" "}
                                                                    {emp.ten_chuc_vu}
                                                                </p>
                                                                <p className="text-sm">
                                                                    <span className="text-muted-foreground">
                                                                        Trạng thái:
                                                                    </span>{" "}
                                                                    {emp.trang_thai}
                                                                </p>
                                                            </div>
                                                            <div className="rounded-lg border bg-card/50 p-3">
                                                                <p className="text-xs text-muted-foreground mb-1">
                                                                    Training Quality
                                                                </p>
                                                                {emp.vector_count === 0 ? (
                                                                    <p className="text-sm text-red-500 font-medium">
                                                                        ⚠️ Chưa có vector — hệ thống sẽ nhận là
                                                                        "Người lạ"
                                                                    </p>
                                                                ) : emp.vector_count < 3 ? (
                                                                    <p className="text-sm text-amber-500 font-medium">
                                                                        ⚠️ Ít dữ liệu — nên thêm 3-5 ảnh
                                                                    </p>
                                                                ) : (
                                                                    <p className="text-sm text-emerald-500 font-medium">
                                                                        ✅ Đủ dữ liệu cho nhận diện chính xác
                                                                    </p>
                                                                )}
                                                            </div>
                                                            <div className="rounded-lg border bg-card/50 p-3">
                                                                <p className="text-xs text-muted-foreground mb-1">
                                                                    Intra Similarity
                                                                </p>
                                                                {emp.intra_similarity ? (
                                                                    <div className="text-sm space-y-0.5">
                                                                        <p>
                                                                            Min:{" "}
                                                                            <span
                                                                                className={`font-mono ${getSimilarityColor(
                                                                                    emp.intra_similarity.min
                                                                                )}`}
                                                                            >
                                                                                {emp.intra_similarity.min.toFixed(4)}
                                                                            </span>
                                                                        </p>
                                                                        <p>
                                                                            Max:{" "}
                                                                            <span
                                                                                className={`font-mono ${getSimilarityColor(
                                                                                    emp.intra_similarity.max
                                                                                )}`}
                                                                            >
                                                                                {emp.intra_similarity.max.toFixed(4)}
                                                                            </span>
                                                                        </p>
                                                                        <p>
                                                                            Avg:{" "}
                                                                            <span
                                                                                className={`font-mono font-bold ${getSimilarityColor(
                                                                                    emp.intra_similarity.avg
                                                                                )}`}
                                                                            >
                                                                                {emp.intra_similarity.avg.toFixed(4)}
                                                                            </span>
                                                                        </p>
                                                                    </div>
                                                                ) : (
                                                                    <p className="text-sm text-muted-foreground">
                                                                        Cần ≥2 vectors
                                                                    </p>
                                                                )}
                                                            </div>
                                                        </div>

                                                        {/* Vector List */}
                                                        {emp.vectors.length > 0 && (
                                                            <div>
                                                                <p className="text-sm font-medium mb-2 flex items-center gap-1.5">
                                                                    <Database className="h-4 w-4" />
                                                                    Vectors ({emp.vectors.length})
                                                                </p>
                                                                <div className="grid gap-2">
                                                                    {emp.vectors.map((vec, idx) => (
                                                                        <div
                                                                            key={idx}
                                                                            className="rounded-lg border bg-card/50 p-3 flex items-center justify-between cursor-pointer hover:bg-accent/30 transition-colors"
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                setSelectedVector(vec);
                                                                            }}
                                                                        >
                                                                            <div className="flex items-center gap-3">
                                                                                <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center">
                                                                                    <Binary className="h-4 w-4 text-primary" />
                                                                                </div>
                                                                                <div>
                                                                                    <p className="text-sm font-mono">
                                                                                        Vector #{idx + 1}{" "}
                                                                                        <span className="text-muted-foreground">
                                                                                            (ID: {vec.embedding_id})
                                                                                        </span>
                                                                                    </p>
                                                                                    <p className="text-xs text-muted-foreground">
                                                                                        {vec.dim}D • Norm: {vec.norm} •{" "}
                                                                                        {vec.is_normalized
                                                                                            ? "✅ Normalized"
                                                                                            : "⚠️ Not normalized"}
                                                                                    </p>
                                                                                </div>
                                                                            </div>
                                                                            <div className="text-right">
                                                                                <p className="text-xs font-mono text-muted-foreground">
                                                                                    [{vec.preview
                                                                                        .slice(0, 4)
                                                                                        .map((v) => v.toFixed(3))
                                                                                        .join(", ")}
                                                                                    , ...]
                                                                                </p>
                                                                                <p className="text-xs text-muted-foreground">
                                                                                    μ={vec.stats.mean.toFixed(4)} σ=
                                                                                    {vec.stats.std.toFixed(4)}
                                                                                </p>
                                                                            </div>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </div>

            {/* Vector Detail Dialog */}
            <Dialog
                open={!!selectedVector}
                onOpenChange={(open) => !open && setSelectedVector(null)}
            >
                <DialogContent className="sm:max-w-[600px]">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Binary className="h-5 w-5" />
                            Chi tiết Vector
                        </DialogTitle>
                    </DialogHeader>
                    {selectedVector && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div className="rounded-lg border p-3">
                                    <p className="text-xs text-muted-foreground">Embedding ID</p>
                                    <p className="font-mono font-bold">
                                        {selectedVector.embedding_id}
                                    </p>
                                </div>
                                <div className="rounded-lg border p-3">
                                    <p className="text-xs text-muted-foreground">Dimensions</p>
                                    <p className="font-mono font-bold">{selectedVector.dim}</p>
                                </div>
                                <div className="rounded-lg border p-3">
                                    <p className="text-xs text-muted-foreground">L2 Norm</p>
                                    <p className="font-mono font-bold">{selectedVector.norm}</p>
                                </div>
                                <div className="rounded-lg border p-3">
                                    <p className="text-xs text-muted-foreground">Normalized</p>
                                    <p className="font-bold">
                                        {selectedVector.is_normalized ? (
                                            <span className="text-emerald-500">✅ Yes</span>
                                        ) : (
                                            <span className="text-red-500">❌ No</span>
                                        )}
                                    </p>
                                </div>
                            </div>

                            <div className="rounded-lg border p-3">
                                <p className="text-xs text-muted-foreground mb-2">
                                    Statistics
                                </p>
                                <div className="grid grid-cols-4 gap-2 text-center">
                                    <div>
                                        <p className="text-xs text-muted-foreground">Min</p>
                                        <p className="font-mono text-sm font-bold text-blue-400">
                                            {selectedVector.stats.min}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-muted-foreground">Max</p>
                                        <p className="font-mono text-sm font-bold text-red-400">
                                            {selectedVector.stats.max}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-muted-foreground">Mean</p>
                                        <p className="font-mono text-sm font-bold">
                                            {selectedVector.stats.mean}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-muted-foreground">Std</p>
                                        <p className="font-mono text-sm font-bold text-amber-400">
                                            {selectedVector.stats.std}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-lg border p-3">
                                <p className="text-xs text-muted-foreground mb-2">
                                    Preview (8 phần tử đầu)
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                    {selectedVector.preview.map((val, i) => (
                                        <span
                                            key={i}
                                            className="inline-block px-2 py-1 rounded bg-muted font-mono text-xs"
                                        >
                                            [{i}] {val.toFixed(4)}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {/* Visual bar chart of preview values */}
                            <div className="rounded-lg border p-3">
                                <p className="text-xs text-muted-foreground mb-2">
                                    Distribution
                                </p>
                                <div className="flex items-end gap-1 h-16">
                                    {selectedVector.preview.map((val, i) => {
                                        const normalized =
                                            ((val - selectedVector.stats.min) /
                                                (selectedVector.stats.max - selectedVector.stats.min || 1)) *
                                            100;
                                        return (
                                            <div
                                                key={i}
                                                className="flex-1 bg-primary/70 rounded-t transition-all"
                                                style={{ height: `${Math.max(4, normalized)}%` }}
                                                title={`[${i}] = ${val.toFixed(4)}`}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </Layout>
    );
}
