export default function DocumentsPanel({ documents, uploading, fileRef, onUpload, onAutoFetch, autoFetching }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-700 mb-3">Uploaded Documents</h2>
      {documents?.length ? (
        <div className="bg-white border border-slate-200 rounded divide-y divide-slate-100 mb-3">
          {documents.map(d => (
            <div key={d} className="flex items-center gap-2 px-3 py-2 text-xs text-slate-700">
              <span className="text-blue-500">📄</span>{d}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-slate-400 text-xs mb-3">No documents uploaded yet.</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <label className={`inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded text-xs cursor-pointer font-medium ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          <input ref={fileRef} type="file" accept=".pdf,.json,.txt,.md" className="hidden" onChange={onUpload} disabled={uploading} />
          {uploading ? 'Uploading…' : '+ Upload document'}
        </label>
        {onAutoFetch && (
          <button
            onClick={onAutoFetch}
            disabled={autoFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-xs font-medium disabled:opacity-50 transition-colors"
          >
            {autoFetching ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Fetching…
              </>
            ) : (
              <>🔍 AutoFetch Company Data</>
            )}
          </button>
        )}
      </div>
      <p className="text-[11px] text-slate-400 mt-1.5">Supported: PDF, JSON, TXT, MD</p>
    </div>
  )
}
