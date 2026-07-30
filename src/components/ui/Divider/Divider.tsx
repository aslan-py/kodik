export function Divider({ className = "" }: { className?: string }) {
    return (
        <hr
            className={` my-5 border-0 h-px bg-(--color-border) ${className}`}
        />
    );
}