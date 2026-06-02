import { File, FileText, Folder, MoreVertical, Upload } from "lucide-react";
import { Button } from "./ui/button";
import { useState, useRef } from "react";

export function DocumentsView({ currentFile }: { currentFile?: string | null }) {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const folders = [
    { id: 1, name: "Rechnungen 2024", count: 12, size: "2.4 MB" },
    { id: 2, name: "Verträge", count: 5, size: "1.1 MB" },
    { id: 3, name: "Projekt Assets", count: 24, size: "15.8 MB" },
  ];

  const files = [
    { id: 1, name: "Jahresbericht_Q1.pdf", type: "PDF", size: "4.2 MB", date: "Heute" },
    { id: 2, name: "Protokoll_Meeting.docx", type: "Word", size: "1.1 MB", date: "Gestern" },
    { id: 3, name: "Finanzplan.xlsx", type: "Excel", size: "850 KB", date: "12. Okt" },
    { id: 4, name: "Logo_Entwurf.png", type: "Image", size: "2.1 MB", date: "10. Okt" },
  ];

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;

    setUploading(true);
    try {
      // TODO: Implement actual file upload to backend
      // For now, just simulate the upload
      await new Promise(resolve => setTimeout(resolve, 1000));
      console.log("Files uploaded:", Array.from(selectedFiles).map(f => f.name));
    } catch (error) {
      console.error("Upload failed:", error);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="h-full p-8 overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-semibold text-white">Dokumente</h2>
          <p className="text-sm text-slate-300">Verwalte Dateien, Ordner und Wissensquellen</p>
          {currentFile ? (
            <div className="mt-2 inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
              Aktive Datei: {currentFile}
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.xlsx,.xls"
          />
          <Button
            onClick={handleUploadClick}
            disabled={uploading}
            className="bg-cyan-400 hover:bg-cyan-300 text-slate-950 gap-2 shadow-lg"
          >
            <Upload className="w-4 h-4" />
            {uploading ? "Wird hochgeladen..." : "Hochladen"}
          </Button>
        </div>
      </div>

      <div className="space-y-8">
        {/* Folders */}
        <section>
          <h3 className="text-lg font-medium text-white mb-4">Ordner</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {folders.map(folder => (
              <div
                key={folder.id}
                className="p-4 rounded-xl backdrop-blur-md bg-white/5 border border-white/10 shadow-sm hover:bg-white/10 transition-colors cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-2 bg-cyan-400/20 rounded-lg group-hover:bg-cyan-400/30 transition-colors">
                    <Folder className="w-6 h-6 text-cyan-300" />
                  </div>
                  <button className="text-slate-400 hover:text-white"><MoreVertical className="w-4 h-4" /></button>
                </div>
                <h4 className="font-semibold text-white mb-1">{folder.name}</h4>
                <div className="text-xs text-slate-400 flex items-center gap-2">
                  <span>{folder.count} Dateien</span>
                  <span>•</span>
                  <span>{folder.size}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Recent Files */}
        <section>
          <h3 className="text-lg font-medium text-white mb-4">Zuletzt hochgeladen</h3>
          <div className="grid grid-cols-1 gap-3">
            {files.map(file => (
              <div
                key={file.id}
                className="flex items-center p-3 rounded-xl backdrop-blur-md bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group cursor-pointer"
              >
                <div className="p-2 bg-white/10 rounded-lg mr-4">
                  {file.type === "PDF" ? <FileText className="w-5 h-5 text-cyan-300" /> : <File className="w-5 h-5 text-cyan-300" />}
                </div>
                <div className="flex-1">
                  <h4 className="font-medium text-white">{file.name}</h4>
                  <p className="text-xs text-slate-400">{file.type}</p>
                </div>
                <div className="text-sm text-slate-400 w-24 hidden md:block">{file.size}</div>
                <div className="text-sm text-slate-400 w-24 hidden md:block">{file.date}</div>
                <button className="text-slate-400 opacity-0 group-hover:opacity-100 hover:text-white transition-opacity p-2">
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
