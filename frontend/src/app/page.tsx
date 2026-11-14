'use client';
import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';

type Turn = { role: 'user' | 'assistant'; content: string };
type Conversation = { id: number; title: string; updated_at: string };
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [signedIn, setSignedIn] = useState(false);

  const getToken = () => typeof window === 'undefined' ? '' : localStorage.getItem('smallllm_token') || '';

  async function loadConversations() {
    const token = getToken();
    setSignedIn(Boolean(token));
    if (!token) return;
    try {
      const response = await fetch(`${API_BASE}/api/conversations/`, {
        headers: { Authorization: `Token ${token}` },
      });
      if (!response.ok) return;
      const data = await response.json();
      setConversations(data.results || data);
    } catch {
      setError('Could not load your saved conversations.');
    }
  }

  useEffect(() => { void loadConversations(); }, []);

  async function openConversation(id: number) {
    const response = await fetch(`${API_BASE}/api/conversations/${id}/`, {
      headers: { Authorization: `Token ${getToken()}` },
    });
    if (!response.ok) {
      setError('Could not open that conversation.');
      return;
    }
    const data = await response.json();
    setConversationId(id);
    setTurns((data.messages || []) as Turn[]);
    setError('');
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = prompt.trim();
    if (!text || busy) return;
    setPrompt('');
    setError('');
    const nextTurns = [...turns, { role: 'user' as const, content: text }];
    setTurns(nextTurns);
    setBusy(true);
    try {
      const token = getToken();
      let activeConversation = conversationId;
      if (token && !activeConversation) {
        const created = await fetch(`${API_BASE}/api/conversations/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Token ${token}` },
          body: JSON.stringify({ title: text.slice(0, 150) }),
        });
        if (!created.ok) throw new Error('Could not create a saved conversation.');
        const conversation = await created.json();
        activeConversation = conversation.id;
        setConversationId(conversation.id);
      }
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = `Token ${token}`;
      const response = await fetch(`${API_BASE}/api/chat/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          messages: nextTurns,
          max_tokens: 700,
          ...(activeConversation ? { conversation_id: activeConversation } : {}),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.error?.message || data?.detail || 'The model could not respond.');
      const answer = data?.choices?.[0]?.message?.content;
      if (typeof answer !== 'string' || !answer.trim()) throw new Error('The model returned an empty response.');
      setTurns((current) => [...current, { role: 'assistant', content: answer }]);
      if (token) await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed.');
      setTurns((current) => current.slice(0, -1));
    } finally {
      setBusy(false);
    }
  }

  function newConversation() {
    setConversationId(null);
    setTurns([]);
    setError('');
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand">small<span>_</span>LLM</div>
      <button className="newchat" onClick={newConversation}>＋　New conversation</button>
      {signedIn && <div style={{ marginTop: 24 }}>
        <div className="eyebrow">YOUR HISTORY</div>
        {conversations.map((item) => <button key={item.id} onClick={() => openConversation(item.id)} className="newchat" style={{ marginTop: 8, textAlign: 'left', fontSize: 12 }}>{item.title}</button>)}
      </div>}
      <div className="side-note">YOUR PRIVATE AI WORKSPACE<br/>Open-weight intelligence. Self-hosted inference. Built for builders.</div>
      <div style={{ marginTop: 20, display: 'grid', gap: 10 }}>
        {signedIn ? <button className="newchat" onClick={() => { localStorage.removeItem('smallllm_token'); setSignedIn(false); setConversations([]); newConversation(); }}>Sign out</button> : <Link href="/login">Sign in</Link>}
        <Link href="/signup">Create account</Link>
        <Link href="/developers">Developer console</Link>
      </div>
    </aside>
    <main className="main">
      <header className="topbar"><span>Chat playground</span><span className="status"><i className="dot"/> Self-hosted model</span></header>
      <section className="content">
        <div className="hero">
          <div className="eyebrow">OPEN MODEL · PRIVATE INFRASTRUCTURE</div>
          <h1>Think without<br/>the limits.</h1>
          <p>Meet small_LLM: an open-model workspace built for thoughtful conversations and developer workflows. Your prompts are processed by our configured inference server.</p>
        </div>
        <div className="messages">
          {turns.map((turn, index) => <article className={`message ${turn.role}`} key={index}><strong>{turn.role === 'user' ? 'You' : 'small_LLM'}</strong><div>{turn.content}</div></article>)}
          {busy && <article className="message">small_LLM is thinking…</article>}
        </div>
        {error && <p role="alert" style={{ color: '#ff9c9c' }}>{error}</p>}
        <form className="composer" onSubmit={send}>
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask anything…" onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); (event.currentTarget.form as HTMLFormElement)?.requestSubmit(); }
          }}/>
          <div className="composer-footer"><span>Enter to send · Shift + Enter for a new line</span><button className="send" disabled={busy || !prompt.trim()}>{busy ? 'Thinking…' : 'Send ↗'}</button></div>
        </form>
        <div className="footer">AI can make mistakes. Verify important information.</div>
      </section>
    </main>
  </div>;
}
