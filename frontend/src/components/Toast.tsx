import { CheckCircle2 } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

const ToastContext = createContext<(message: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<number>();

  const show = useCallback((m: string) => {
    setMessage(m);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setMessage(null), 2600);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {message && (
        <div className="pointer-events-none fixed inset-x-0 top-4 z-[60] flex justify-center px-4" role="status">
          <div className="flex animate-rise items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white shadow-soft">
            <CheckCircle2 className="h-4 w-4 text-rose-300" />
            {message}
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
