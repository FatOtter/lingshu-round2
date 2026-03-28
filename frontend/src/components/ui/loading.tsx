import { cn } from "@/lib/utils";

interface LoadingProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  text?: string;
}

const SIZES = {
  sm: "size-4 border-2",
  md: "size-8 border-4",
  lg: "size-12 border-4",
};

export function Loading({ className, size = "md", text }: LoadingProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2", className)}>
      <div
        className={cn(
          "animate-spin rounded-full border-primary border-t-transparent",
          SIZES[size],
        )}
      />
      {text && <p className="text-sm text-muted-foreground">{text}</p>}
    </div>
  );
}

export function PageLoading() {
  return (
    <div className="flex flex-1 items-center justify-center py-20">
      <Loading size="lg" text="Loading..." />
    </div>
  );
}
