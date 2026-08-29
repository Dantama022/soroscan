import * as React from "react"

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = React.useRef<HTMLElement | null>(null);

  React.useEffect(() => {
    if (!isOpen) return;

    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;

    const getFocusable = () =>
      Array.from(
        containerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
      );

    const focusable = getFocusable();
    (focusable[0] ?? containerRef.current)?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }

      if (e.key !== "Tab") return;

      const elements = getFocusable();
      if (elements.length === 0) {
        e.preventDefault();
        return;
      }

      const first = elements[0];
      const last = elements[elements.length - 1];
      const active = document.activeElement;

      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      {/* Dark Overlay */}
      <div
        className="absolute inset-0 bg-terminal-black/80 backdrop-blur-sm cursor-pointer"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-label={title || "MESSAGE"}
        tabIndex={-1}
        className="relative w-full max-w-lg border-terminal border-terminal-green bg-terminal-black p-1 shadow-glow-green/30 animate-in zoom-in-95 duration-200 max-h-[90vh] flex flex-col outline-none"
      >
        {/* Box corners */}
        <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-terminal-green" />
        <div className="absolute top-0 right-0 w-2 h-2 border-t-2 border-r-2 border-terminal-green" />
        <div className="absolute bottom-0 left-0 w-2 h-2 border-b-2 border-l-2 border-terminal-green" />
        <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-terminal-green" />

        {/* Modal Header */}
        <div className="bg-terminal-green text-terminal-black px-4 py-2 font-terminal-mono font-bold flex justify-between items-center flex-shrink-0">
          <span className="text-sm sm:text-base">[{title || "MESSAGE"}]</span>
          <button
            onClick={onClose}
            className="hover:scale-110 transition-transform cursor-pointer min-w-[44px] min-h-[44px] flex items-center justify-center"
          >
            [X]
          </button>
        </div>

        {/* Modal Content — scrollable on small screens */}
        <div className="p-3 sm:p-6 font-terminal-mono text-terminal-green border border-terminal-green/30 m-1 overflow-y-auto">
          {children}
        </div>

        {/* Modal Footer */}
        <div className="h-4 bg-terminal-green/10 flex items-center px-4 justify-between border-t border-terminal-green/30 flex-shrink-0">
          <div className="text-[10px] text-terminal-green/50">SYSTEM_AUTH_REQUIRED</div>
          <div className="flex gap-2">
            <div className="w-1 h-1 bg-terminal-green animate-pulse" />
            <div className="w-1 h-1 bg-terminal-green animate-pulse delay-75" />
            <div className="w-1 h-1 bg-terminal-green animate-pulse delay-150" />
          </div>
        </div>
      </div>
    </div>
  );
};

export { Modal }
