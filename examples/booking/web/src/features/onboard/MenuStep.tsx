import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/Button";
import { uploadDoc, type UploadedDoc } from "@/lib/api/admin-v2";

/**
 * Optional step between install and done — upload a menu PDF so the
 * enquiry agent can answer grounded questions. The merchant's onboard
 * cookie satisfies /v1/admin/tenants/{tid}/docs as of slice 6.
 */
export function MenuStep({
  tenantId,
  onDone,
}: {
  tenantId: string;
  onDone: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploaded, setUploaded] = useState<UploadedDoc | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => uploadDoc(tenantId, file),
    onSuccess: setUploaded,
  });

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold text-ink-700">Upload your menu (PDF)</h1>
      <p className="text-sm text-ink-200">
        Optional — lets your agent answer questions like "do you have gluten-free
        pizza?" straight from your menu. PDF or plain text, up to a few MB.
      </p>

      {uploaded ? (
        <div className="rounded-md border border-ink-700 bg-white px-4 py-3">
          <p className="text-sm font-medium text-ink-700">{uploaded.name}</p>
          <p className="mt-0.5 text-xs text-ink-100">
            Indexed into {uploaded.chunks} chunk{uploaded.chunks === 1 ? "" : "s"}.
          </p>
        </div>
      ) : (
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt"
          aria-label="Menu file"
          className="text-sm text-ink-200 file:mr-3 file:rounded-md file:border file:border-paper-600 file:bg-paper-200 file:px-3 file:py-1.5 file:text-sm file:text-ink-700"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
          }}
        />
      )}

      {upload.isPending && <p className="text-sm text-ink-200">Uploading…</p>}
      {upload.isError && (
        <p className="text-sm text-rust">{(upload.error as Error).message}</p>
      )}

      <div className="flex items-center gap-3">
        {uploaded ? (
          <Button onClick={onDone}>Continue</Button>
        ) : (
          <button
            type="button"
            onClick={onDone}
            className="text-sm text-ink-200 underline underline-offset-2 hover:text-ink-700"
          >
            Skip for now
          </button>
        )}
      </div>
    </div>
  );
}
