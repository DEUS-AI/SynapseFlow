import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, FileText, Download, Copy, Check, Maximize2, Minimize2 } from 'lucide-react';

interface DocumentPreviewTabProps {
  docId: string;
}

interface DocumentContent {
  content: string;
  content_type: string;
  size_bytes?: number;
  word_count?: number;
}

export function DocumentPreviewTab({ docId }: DocumentPreviewTabProps) {
  const [content, setContent] = useState<DocumentContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    async function loadContent() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(`/api/admin/documents/${docId}/content`);
        if (!response.ok) {
          if (response.status === 404) {
            setError('Document content not found');
            return;
          }
          throw new Error('Failed to load document content');
        }

        const data = await response.json();
        setContent(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load content');
      } finally {
        setLoading(false);
      }
    }

    loadContent();
  }, [docId]);

  const handleCopy = async () => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleDownload = () => {
    if (!content) return;
    const blob = new Blob([content.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${docId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-slate-400">Loading document content...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="w-12 h-12 text-red-500" />
          <div>
            <h3 className="text-lg font-medium text-slate-200">Error Loading Content</h3>
            <p className="text-slate-400 mt-2">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4 text-center">
          <FileText className="w-12 h-12 text-slate-600" />
          <div>
            <h3 className="text-lg font-medium text-slate-200">No Content Available</h3>
            <p className="text-slate-400 mt-2">
              This document's content is not available for preview.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col ${isFullscreen ? 'fixed inset-0 z-50 bg-slate-900 p-6' : 'h-full'}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-medium text-slate-200">Document Preview</h2>
          <div className="flex items-center gap-3 text-sm text-slate-400">
            {content.word_count && (
              <span>{content.word_count.toLocaleString()} words</span>
            )}
            {content.size_bytes && (
              <span>{formatBytes(content.size_bytes)}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors text-sm"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-green-400" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                Copy
              </>
            )}
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors text-sm"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors text-sm"
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-slate-800/50 rounded-lg border border-slate-700">
        <div className="p-6">
          <MarkdownRenderer content={content.content} />
        </div>
      </div>
    </div>
  );
}

// Simple markdown renderer
function MarkdownRenderer({ content }: { content: string }) {
  // Parse and render markdown content
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeContent: string[] = [];
  let codeLanguage = '';

  lines.forEach((line, index) => {
    // Code block handling
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={`code-${index}`} className="bg-slate-900 rounded-lg p-4 overflow-x-auto my-4 text-sm">
            <code className="text-slate-300">{codeContent.join('\n')}</code>
          </pre>
        );
        codeContent = [];
        inCodeBlock = false;
      } else {
        codeLanguage = line.slice(3);
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeContent.push(line);
      return;
    }

    // Headers
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={index} className="text-2xl font-bold text-slate-100 mt-6 mb-4 first:mt-0">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={index} className="text-xl font-semibold text-slate-100 mt-5 mb-3">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith('### ')) {
      elements.push(
        <h3 key={index} className="text-lg font-medium text-slate-200 mt-4 mb-2">
          {line.slice(4)}
        </h3>
      );
    } else if (line.startsWith('#### ')) {
      elements.push(
        <h4 key={index} className="text-base font-medium text-slate-300 mt-3 mb-2">
          {line.slice(5)}
        </h4>
      );
    }
    // Horizontal rule
    else if (line.match(/^[-*_]{3,}$/)) {
      elements.push(<hr key={index} className="border-slate-600 my-6" />);
    }
    // Bullet list
    else if (line.match(/^[-*+]\s/)) {
      elements.push(
        <li key={index} className="text-slate-300 ml-4 list-disc">
          {renderInlineMarkdown(line.slice(2))}
        </li>
      );
    }
    // Numbered list
    else if (line.match(/^\d+\.\s/)) {
      const content = line.replace(/^\d+\.\s/, '');
      elements.push(
        <li key={index} className="text-slate-300 ml-4 list-decimal">
          {renderInlineMarkdown(content)}
        </li>
      );
    }
    // Blockquote
    else if (line.startsWith('> ')) {
      elements.push(
        <blockquote key={index} className="border-l-4 border-blue-500 pl-4 italic text-slate-400 my-3">
          {renderInlineMarkdown(line.slice(2))}
        </blockquote>
      );
    }
    // Empty line
    else if (line.trim() === '') {
      elements.push(<div key={index} className="h-4" />);
    }
    // Regular paragraph
    else {
      elements.push(
        <p key={index} className="text-slate-300 leading-relaxed my-2">
          {renderInlineMarkdown(line)}
        </p>
      );
    }
  });

  return <div className="prose prose-invert max-w-none">{elements}</div>;
}

// Render inline markdown (bold, italic, code, links)
function renderInlineMarkdown(text: string): React.ReactNode {
  // Simple inline markdown parsing
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Inline code
    const codeMatch = remaining.match(/^`([^`]+)`/);
    if (codeMatch) {
      parts.push(
        <code key={key++} className="bg-slate-700 px-1.5 py-0.5 rounded text-sm text-blue-300">
          {codeMatch[1]}
        </code>
      );
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }

    // Bold
    const boldMatch = remaining.match(/^\*\*([^*]+)\*\*/);
    if (boldMatch) {
      parts.push(<strong key={key++} className="font-semibold text-slate-100">{boldMatch[1]}</strong>);
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }

    // Italic
    const italicMatch = remaining.match(/^\*([^*]+)\*/);
    if (italicMatch) {
      parts.push(<em key={key++} className="italic">{italicMatch[1]}</em>);
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }

    // Link
    const linkMatch = remaining.match(/^\[([^\]]+)\]\(([^)]+)\)/);
    if (linkMatch) {
      parts.push(
        <a
          key={key++}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:text-blue-300 underline"
        >
          {linkMatch[1]}
        </a>
      );
      remaining = remaining.slice(linkMatch[0].length);
      continue;
    }

    // Regular text - take characters until we hit a special character
    const textMatch = remaining.match(/^[^`*\[]+/);
    if (textMatch) {
      parts.push(textMatch[0]);
      remaining = remaining.slice(textMatch[0].length);
    } else {
      // Single special character that's not part of a pattern
      parts.push(remaining[0]);
      remaining = remaining.slice(1);
    }
  }

  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
