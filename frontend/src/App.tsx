import { useState } from 'react';
import Upload from './pages/Upload';
import Findings from './pages/Findings';

type Page = 'upload' | 'findings';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('upload');

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Navigation */}
      <nav className="border-b border-white/10 backdrop-blur-md bg-white/5 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            Compliance Engine
          </h1>
          <div className="flex gap-1 bg-white/5 rounded-xl p-1">
            <button
              id="nav-upload"
              onClick={() => setCurrentPage('upload')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
                currentPage === 'upload'
                  ? 'bg-cyan-500/20 text-cyan-300 shadow-lg shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              Upload
            </button>
            <button
              id="nav-findings"
              onClick={() => setCurrentPage('findings')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
                currentPage === 'findings'
                  ? 'bg-cyan-500/20 text-cyan-300 shadow-lg shadow-cyan-500/10'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              Findings
            </button>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="max-w-7xl mx-auto px-6 py-10">
        {currentPage === 'upload' && (
          <Upload onNavigateToFindings={() => setCurrentPage('findings')} />
        )}
        {currentPage === 'findings' && (
          <Findings onNavigateToUpload={() => setCurrentPage('upload')} />
        )}
      </main>
    </div>
  );
}

export default App;
