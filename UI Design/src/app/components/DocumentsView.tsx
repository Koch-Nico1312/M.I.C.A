import { File, FileText, Folder, MoreVertical, Upload } from "lucide-react";
import { Button } from "./ui/button";

export function DocumentsView() {
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

  return (
    <div className="h-full p-8 overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-semibold text-[#395886]">Dokumente</h2>
          <p className="text-sm text-[#8AAEE0]">Verwalten Sie Ihre Dateien und Ordner</p>
        </div>
        <Button className="bg-[#638ECB] hover:bg-[#395886] text-white gap-2 shadow-lg">
          <Upload className="w-4 h-4" />
          Hochladen
        </Button>
      </div>

      <div className="space-y-8">
        {/* Folders */}
        <section>
          <h3 className="text-lg font-medium text-[#395886] mb-4">Ordner</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {folders.map(folder => (
              <div 
                key={folder.id} 
                className="p-4 rounded-xl backdrop-blur-md bg-white/30 border border-white/40 shadow-sm hover:bg-white/40 transition-colors cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-2 bg-[#638ECB]/20 rounded-lg group-hover:bg-[#638ECB]/30 transition-colors">
                    <Folder className="w-6 h-6 text-[#638ECB]" />
                  </div>
                  <button className="text-[#8AAEE0] hover:text-[#395886]"><MoreVertical className="w-4 h-4" /></button>
                </div>
                <h4 className="font-semibold text-[#395886] mb-1">{folder.name}</h4>
                <div className="text-xs text-[#8AAEE0] flex items-center gap-2">
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
          <h3 className="text-lg font-medium text-[#395886] mb-4">Zuletzt hochgeladen</h3>
          <div className="grid grid-cols-1 gap-3">
            {files.map(file => (
              <div 
                key={file.id} 
                className="flex items-center p-3 rounded-xl backdrop-blur-md bg-white/20 border border-white/30 hover:bg-white/30 transition-colors group cursor-pointer"
              >
                <div className="p-2 bg-white/50 rounded-lg mr-4">
                  {file.type === "PDF" ? <FileText className="w-5 h-5 text-[#638ECB]" /> : <File className="w-5 h-5 text-[#638ECB]" />}
                </div>
                <div className="flex-1">
                  <h4 className="font-medium text-[#395886]">{file.name}</h4>
                  <p className="text-xs text-[#8AAEE0]">{file.type}</p>
                </div>
                <div className="text-sm text-[#8AAEE0] w-24 hidden md:block">{file.size}</div>
                <div className="text-sm text-[#8AAEE0] w-24 hidden md:block">{file.date}</div>
                <button className="text-[#8AAEE0] opacity-0 group-hover:opacity-100 hover:text-[#395886] transition-opacity p-2">
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
