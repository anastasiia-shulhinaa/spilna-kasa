import { Camera, FolderOpen, Images } from "lucide-react";
import { useRef, useState } from "react";
import { Button, cn } from "./ui";

const ACCEPT = "image/jpeg,image/png,image/webp";

/** Телефон чи планшет: сенсорний екран без точного вказівника або мобільний браузер. */
export function isMobileDevice(): boolean {
  if (typeof window === "undefined") return false;
  const coarse = window.matchMedia?.("(pointer: coarse)").matches ?? false;
  const mobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
  return coarse && mobileUa;
}

/**
 * Вибір фото чека.
 * На телефоні — дві кнопки: «Сфотографувати» (одразу відкриває камеру) і «З галереї».
 * На комп'ютері — одна кнопка «Обрати файл».
 */
export function PhotoPicker({
  onPick,
  label = "фото чека",
  busy,
  compact,
}: {
  onPick: (file: File) => void;
  label?: string;
  busy?: boolean;
  compact?: boolean;
}) {
  const [mobile] = useState(isMobileDevice);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handle = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) onPick(file);
  };
  const size = compact ? "px-4 py-2 text-sm" : "";

  return (
    <div className={cn("flex flex-wrap gap-2", !compact && "w-full")}>
      {mobile ? (
        <>
          <input ref={cameraRef} type="file" accept={ACCEPT} capture="environment" className="hidden" onChange={handle} />
          <input ref={galleryRef} type="file" accept={ACCEPT} className="hidden" onChange={handle} />
          <Button type="button" className={cn(!compact && "flex-1", size)} loading={busy} onClick={() => cameraRef.current?.click()}>
            <Camera className="h-4 w-4" /> Сфотографувати
          </Button>
          <Button type="button" variant="outline" className={cn(!compact && "flex-1", size)} disabled={busy} onClick={() => galleryRef.current?.click()}>
            <Images className="h-4 w-4" /> З галереї
          </Button>
        </>
      ) : (
        <>
          <input ref={fileRef} type="file" accept={ACCEPT} className="hidden" onChange={handle} />
          <Button type="button" variant="outline" className={cn(!compact && "flex-1", size)} loading={busy} onClick={() => fileRef.current?.click()}>
            <FolderOpen className="h-4 w-4" /> Обрати файл ({label})
          </Button>
        </>
      )}
    </div>
  );
}
