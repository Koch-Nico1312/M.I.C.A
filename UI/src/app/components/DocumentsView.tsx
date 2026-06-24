import {
  AlertCircle,
  CheckCircle2,
  File,
  FileText,
  Folder,
  Loader2,
  MoreVertical,
  SearchCheck,
  Upload,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { jarvisApi } from "../lib/api";
import type { DocumentRecord } from "../lib/types";

type UploadState = "idle" | "uploading" | "done" | "error";

function formatUploadSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function fileKind(name: string) {
  const extension = name.split(".").pop()?.toUpperCase();
  return extension || "FILE";
}

export function DocumentsView({ currentFile }: { currentFile?: string | null }) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [dragActive, setDragActive] = useState(false);
  const [analyze, setAnalyze] = useState(true);
  const [index, setIndex] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const folders = [
    { id: 1, name: "Uploads", count: documents.length, size: documents.length ? `${documents.length} Dateien` : "Leer" },
    { id: 2, name: "Analysen", count: documents.filter((file) => file.analysis).length, size: "Metadaten" },
    { id: 3, name: "Index", count: documents.filter((file) => file.indexed).length, size: "Suche" },
  ];

  const refreshDocuments = async () => {
    const payload = await jarvisApi.getDocuments();
    setDocuments(payload.files ?? []);
  };

  useEffect(() => {
    refreshDocuments().catch((err) => {
      setError(err instanceof Error ? err.message : "Dokumente konnten nicht geladen werden.");
    });
  }, []);

  const addFiles = (files: FileList | File[]) => {
    const next = Array.from(files);
    if (!next.length) return;
    setSelectedFiles((previous) => {
      const seen = new Set(previous.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      const merged = [...previous];
      for (const file of next) {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (!seen.has(key)) {
          seen.add(key);
          merged.push(file);
        }
      }
      return merged;
    });
    setError(null);
    setUploadState("idle");
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      addFiles(event.target.files);
    }
    event.target.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    if (event.dataTransfer.files) {
      addFiles(event.dataTransfer.files);
    }
  };

  const uploadSelected = async () => {
    if (!selectedFiles.length) {
      handleUploadClick();
      return;
    }

    setUploadState("uploading");
    setError(null);
    try {
      const result = await jarvisApi.uploadDocuments(selectedFiles, { analyze, index });
      setDocuments(result.files ?? []);
      setSelectedFiles([]);
      setUploadState(result.errors?.length ? "error" : "done");
      if (result.errors?.length) {
        setError(result.errors.map((item) => `${item.name}: ${item.error}`).join("\n"));
      }
      await refreshDocuments();
    } catch (err) {
      setUploadState("error");
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
    }
  };

  const recentFiles = documents.length
    ? documents
    : [
        { id: "sample-1", name: "Jahresbericht_Q1.pdf", type: "PDF", size: 4404019, size_label: "4.2 MB", uploaded_at: "Heute", indexed: false },
        { id: "sample-2", name: "Protokoll_Meeting.docx", type: "DOCX", size: 1153434, size_label: "1.1 MB", uploaded_at: "Gestern", indexed: false },
      ];

  return (
    <div className="h-full overflow-y-auto p-5 md:p-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Dokumente</h2>
          {currentFile ? (
            <div className="mt-2 inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
              Aktive Datei: {currentFile}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
            <Checkbox checked={analyze} onCheckedChange={(value) => setAnalyze(value === true)} />
            Analysieren
          </label>
          <label className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
            <Checkbox checked={index} onCheckedChange={(value) => setIndex(value === true)} />
            Indexieren
          </label>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.xlsx,.xls,.csv,.json"
          />
          <Button
            onClick={uploadSelected}
            disabled={uploadState === "uploading"}
            className="gap-2 rounded-xl bg-cyan-400 text-slate-950 shadow-lg hover:bg-cyan-300"
          >
            {uploadState === "uploading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {selectedFiles.length ? `${selectedFiles.length} hochladen` : "Hochladen"}
          </Button>
        </div>
      </div>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`mb-6 rounded-2xl border border-dashed p-5 transition ${
          dragActive ? "border-cyan-300 bg-cyan-400/10" : "border-white/15 bg-white/[0.04]"
        }`}
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 p-3">
              <Upload className="h-6 w-6 text-cyan-200" />
            </div>
            <div>
              <div className="font-medium text-white">
                {selectedFiles.length ? `${selectedFiles.length} Datei(en) bereit` : "Dateien ablegen"}
              </div>
              <div className="text-sm text-slate-400">
                {selectedFiles.length
                  ? selectedFiles.map((file) => file.name).slice(0, 2).join(", ")
                  : "PDF, Office, Text, Bilder und Tabellen"}
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            onClick={handleUploadClick}
            className="rounded-xl border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10 hover:text-white"
          >
            <FileText className="h-4 w-4" />
            Auswaehlen
          </Button>
        </div>

        {selectedFiles.length ? (
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {selectedFiles.slice(0, 6).map((file) => (
              <div key={`${file.name}-${file.size}-${file.lastModified}`} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300">
                <div className="truncate text-white">{file.name}</div>
                <div className="text-xs text-slate-500">{formatUploadSize(file.size)}</div>
              </div>
            ))}
          </div>
        ) : null}

        {uploadState === "done" ? (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-sm text-emerald-100">
            <CheckCircle2 className="h-4 w-4" />
            Upload abgeschlossen
          </div>
        ) : null}
        {error ? (
          <div className="mt-4 flex items-start gap-2 whitespace-pre-line rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </div>
        ) : null}
      </div>

      <div className="space-y-8">
        <section>
          <h3 className="mb-4 text-lg font-medium text-white">Ordner</h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {folders.map((folder) => (
              <div
                key={folder.id}
                className="group cursor-pointer rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm transition-colors hover:bg-white/10"
              >
                <div className="mb-3 flex items-start justify-between">
                  <div className="rounded-lg bg-cyan-400/20 p-2 transition-colors group-hover:bg-cyan-400/30">
                    <Folder className="h-6 w-6 text-cyan-300" />
                  </div>
                  <button className="text-slate-400 hover:text-white">
                    <MoreVertical className="h-4 w-4" />
                  </button>
                </div>
                <h4 className="mb-1 font-semibold text-white">{folder.name}</h4>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span>{folder.count} Dateien</span>
                  <span>|</span>
                  <span>{folder.size}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h3 className="mb-4 text-lg font-medium text-white">Zuletzt hochgeladen</h3>
          <div className="grid grid-cols-1 gap-3">
            {recentFiles.map((file) => (
              <div
                key={file.id}
                className="group flex items-center rounded-2xl border border-white/10 bg-white/5 p-3 transition-colors hover:bg-white/10"
              >
                <div className="mr-4 rounded-lg bg-white/10 p-2">
                  {file.type === "PDF" ? <FileText className="h-5 w-5 text-cyan-300" /> : <File className="h-5 w-5 text-cyan-300" />}
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="truncate font-medium text-white">{file.name}</h4>
                  <p className="text-xs text-slate-400">{file.type || fileKind(file.name)}</p>
                </div>
                <div className="hidden w-24 text-sm text-slate-400 md:block">{file.size_label}</div>
                <div className="hidden w-36 text-sm text-slate-400 md:block">
                  {file.uploaded_at.includes("T") ? new Date(file.uploaded_at).toLocaleDateString() : file.uploaded_at}
                </div>
                <div className="hidden w-24 items-center gap-1 text-xs text-slate-300 md:flex">
                  <SearchCheck className={`h-4 w-4 ${file.indexed ? "text-emerald-300" : "text-slate-500"}`} />
                  {file.indexed ? "Index" : "Datei"}
                </div>
                <button className="p-2 text-slate-400 opacity-0 transition-opacity hover:text-white group-hover:opacity-100">
                  <MoreVertical className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
