export function Divider({ className = "" }: { className?: string }) {
    return (
        <hr
            className={`border-0 h-px bg-(--color-border) ${className}`}
        />
    );
}