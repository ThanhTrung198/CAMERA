import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface StatusCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  alert?: boolean;
}

export default function StatusCard({
  title,
  value,
  icon: Icon,
  description,
  trend,
  trendValue,
  alert = false,
}: StatusCardProps) {
  return (
    <Card className={cn("hover:shadow-md transition-all duration-300 border-l-4", 
      alert ? "border-l-destructive bg-destructive/5" : "border-l-primary"
    )}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className={cn("h-4 w-4", alert ? "text-destructive" : "text-primary")} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold font-mono tracking-tight">{value}</div>
        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
          {description}
          {trend && (
            <span className={cn(
              "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium",
              trend === "up" ? "bg-emerald-500/10 text-emerald-500" : 
              trend === "down" ? "bg-rose-500/10 text-rose-500" : 
              "bg-slate-500/10 text-slate-500"
            )}>
              {trendValue}
            </span>
          )}
        </p>
      </CardContent>
    </Card>
  );
}