import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { sceneApi, systemApi } from '../api';
import type { Scene, SystemInfo } from '../types';

export default function DashboardPage() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'mine'>('all');

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    loadData();
  }, [isAuthenticated, activeTab]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [scenesData, info] = await Promise.all([
        sceneApi.list(activeTab === 'mine'),
        systemApi.getInfo(),
      ]);
      setScenes(scenesData.items);
      setSystemInfo(info);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this scene?')) return;
    try {
      await sceneApi.delete(id);
      setScenes(scenes.filter(s => s.id !== id));
    } catch (err) {
      alert('Failed to delete scene');
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    return (bytes / 1024 / 1024 / 1024).toFixed(1) + ' GB';
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerContent}>
          <h1 style={styles.logo}>3DGS Demo</h1>
          <div style={styles.userSection}>
            <span style={styles.userName}>{user?.username}</span>
            <button onClick={logout} style={styles.logoutBtn}>Logout</button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={styles.main}>
        {/* System Info Card */}
        {systemInfo && (
          <div style={styles.infoCard}>
            <h2 style={styles.infoTitle}>System Information</h2>
            <div style={styles.features}>
              {systemInfo.features.map((f, i) => (
                <span key={i} style={styles.featureTag}>{f}</span>
              ))}
            </div>
          </div>
        )}

        {/* Controls */}
        <div style={styles.controls}>
          <div style={styles.tabs}>
            <button
              onClick={() => setActiveTab('all')}
              style={{
                ...styles.tab,
                ...(activeTab === 'all' ? styles.tabActive : {}),
              }}
            >
              All Scenes
            </button>
            <button
              onClick={() => setActiveTab('mine')}
              style={{
                ...styles.tab,
                ...(activeTab === 'mine' ? styles.tabActive : {}),
              }}
            >
              My Scenes
            </button>
          </div>
          <button onClick={() => setShowUpload(true)} style={styles.uploadBtn}>
            + Upload Scene
          </button>
        </div>

        {/* Scene Grid */}
        {loading ? (
          <div style={styles.loading}>Loading scenes...</div>
        ) : scenes.length === 0 ? (
          <div style={styles.empty}>
            <p>No scenes found. Upload your first 3D Gaussian Splatting scene!</p>
            <button onClick={() => setShowUpload(true)} style={styles.uploadBtn}>
              Upload Scene
            </button>
          </div>
        ) : (
          <div style={styles.grid}>
            {scenes.map(scene => (
              <div key={scene.id} style={styles.card}>
                <div style={styles.cardHeader}>
                  <h3 style={styles.cardTitle}>{scene.name}</h3>
                  {scene.is_public && <span style={styles.publicBadge}>Public</span>}
                </div>
                
                {scene.description && (
                  <p style={styles.description}>{scene.description}</p>
                )}

                <div style={styles.meta}>
                  <div style={styles.metaItem}>
                    <span style={styles.metaLabel}>Format</span>
                    <span style={styles.metaValue}>{scene.file_format.toUpperCase()}</span>
                  </div>
                  <div style={styles.metaItem}>
                    <span style={styles.metaLabel}>Size</span>
                    <span style={styles.metaValue}>{formatFileSize(scene.file_size)}</span>
                  </div>
                  <div style={styles.metaItem}>
                    <span style={styles.metaLabel}>Gaussians</span>
                    <span style={styles.metaValue}>
                      {scene.num_gaussians?.toLocaleString() || 'N/A'}
                    </span>
                  </div>
                  <div style={styles.metaItem}>
                    <span style={styles.metaLabel}>Views</span>
                    <span style={styles.metaValue}>{scene.view_count}</span>
                  </div>
                </div>

                {scene.scene_scale && (
                  <div style={styles.scaleInfo}>
                    Scene Scale: {scene.scene_scale.toFixed(4)}
                    {scene.has_sh && ` | SH Degree: ${scene.sh_degree}`}
                  </div>
                )}

                <div style={styles.cardFooter}>
                  <span style={styles.date}>{formatDate(scene.created_at)}</span>
                  <div style={styles.actions}>
                    <button
                      onClick={() => navigate(`/viewer/${scene.id}`)}
                      style={styles.viewBtn}
                    >
                      View 3D
                    </button>
                    {scene.owner_id === user?.id && (
                      <button
                        onClick={() => handleDelete(scene.id)}
                        style={styles.deleteBtn}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Upload Modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSuccess={() => {
            setShowUpload(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}

// Upload Modal Component
function UploadModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({ name: '', description: '', is_public: false });
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('name', form.name);
    formData.append('description', form.description);
    formData.append('is_public', String(form.is_public));
    formData.append('file', file);

    try {
      await sceneApi.upload(formData);
      onSuccess();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={modalStyles.modal} onClick={e => e.stopPropagation()}>
        <h2 style={modalStyles.title}>Upload 3DGS Scene</h2>
        <form onSubmit={handleSubmit} style={modalStyles.form}>
          <div style={styles.field}>
            <label style={styles.label}>Scene Name *</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })}
              style={styles.input}
              required
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Description</label>
            <textarea
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              style={{ ...styles.input, minHeight: '80px', resize: 'vertical' }}
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Scene File * (PLY, SPLAT, KSPLAT)</label>
            <input
              type="file"
              accept=".ply,.splat,.ksplat"
              onChange={e => setFile(e.target.files?.[0] || null)}
              style={{ ...styles.input, padding: '8px' }}
              required
            />
            {file && <span style={modalStyles.fileInfo}>Selected: {file.name} ({(file.size/1024/1024).toFixed(1)} MB)</span>}
          </div>
          <label style={modalStyles.checkbox}>
            <input
              type="checkbox"
              checked={form.is_public}
              onChange={e => setForm({ ...form, is_public: e.target.checked })}
            />
            Make this scene public
          </label>
          <div style={modalStyles.buttons}>
            <button type="button" onClick={onClose} style={modalStyles.cancelBtn}>Cancel</button>
            <button
              type="submit"
              style={{
                ...modalStyles.submitBtn,
                opacity: uploading ? 0.7 : 1,
              }}
              disabled={uploading || !file}
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const modalStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '20px',
  },
  modal: {
    background: '#1a1a2e',
    borderRadius: '16px',
    padding: '30px',
    width: '100%',
    maxWidth: '500px',
    border: '1px solid rgba(255,255,255,0.1)',
  },
  title: {
    fontSize: '20px',
    fontWeight: 600,
    marginBottom: '20px',
    color: '#fff',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  fileInfo: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.5)',
    marginTop: '4px',
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
    color: 'rgba(255,255,255,0.7)',
    cursor: 'pointer',
  },
  buttons: {
    display: 'flex',
    gap: '12px',
    marginTop: '10px',
  },
  cancelBtn: {
    flex: 1,
    padding: '12px',
    borderRadius: '8px',
    border: '1px solid rgba(255,255,255,0.2)',
    background: 'transparent',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '14px',
  },
  submitBtn: {
    flex: 1,
    padding: '12px',
    borderRadius: '8px',
    border: 'none',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 500,
  },
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    background: '#0a0a0f',
  },
  header: {
    background: 'rgba(255,255,255,0.03)',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
    padding: '0 24px',
  },
  headerContent: {
    maxWidth: '1400px',
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    height: '64px',
  },
  logo: {
    fontSize: '22px',
    fontWeight: 700,
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  userSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  userName: {
    fontSize: '14px',
    color: 'rgba(255,255,255,0.7)',
  },
  logoutBtn: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid rgba(255,255,255,0.2)',
    background: 'transparent',
    color: '#fff',
    fontSize: '13px',
    cursor: 'pointer',
  },
  main: {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '24px',
  },
  infoCard: {
    background: 'rgba(255,255,255,0.03)',
    borderRadius: '12px',
    padding: '20px',
    marginBottom: '24px',
    border: '1px solid rgba(255,255,255,0.08)',
  },
  infoTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '12px',
    color: '#fff',
  },
  features: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  },
  featureTag: {
    padding: '4px 12px',
    borderRadius: '20px',
    background: 'rgba(102,126,234,0.15)',
    color: '#667eea',
    fontSize: '12px',
    fontWeight: 500,
  },
  controls: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
  },
  tabs: {
    display: 'flex',
    gap: '8px',
  },
  tab: {
    padding: '10px 20px',
    borderRadius: '8px',
    border: 'none',
    background: 'transparent',
    color: 'rgba(255,255,255,0.5)',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  tabActive: {
    background: 'rgba(102,126,234,0.2)',
    color: '#667eea',
    fontWeight: 500,
  },
  uploadBtn: {
    padding: '10px 20px',
    borderRadius: '8px',
    border: 'none',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
  },
  loading: {
    textAlign: 'center',
    padding: '60px',
    color: 'rgba(255,255,255,0.5)',
  },
  empty: {
    textAlign: 'center',
    padding: '80px 20px',
    color: 'rgba(255,255,255,0.5)',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
    gap: '20px',
  },
  card: {
    background: 'rgba(255,255,255,0.03)',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid rgba(255,255,255,0.08)',
    transition: 'transform 0.2s, box-shadow 0.2s',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '10px',
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#fff',
    margin: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  publicBadge: {
    padding: '2px 8px',
    borderRadius: '12px',
    background: 'rgba(34,197,94,0.15)',
    color: '#22c55e',
    fontSize: '11px',
    fontWeight: 500,
    flexShrink: 0,
  },
  description: {
    fontSize: '13px',
    color: 'rgba(255,255,255,0.5)',
    marginBottom: '14px',
    lineHeight: 1.5,
    overflow: 'hidden',
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
  },
  meta: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '8px',
    marginBottom: '12px',
  },
  metaItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  metaLabel: {
    fontSize: '11px',
    color: 'rgba(255,255,255,0.35)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  metaValue: {
    fontSize: '13px',
    color: 'rgba(255,255,255,0.8)',
    fontWeight: 500,
  },
  scaleInfo: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.4)',
    marginBottom: '14px',
    padding: '6px 10px',
    background: 'rgba(255,255,255,0.03)',
    borderRadius: '6px',
  },
  cardFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: '14px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
  },
  date: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.35)',
  },
  actions: {
    display: 'flex',
    gap: '8px',
  },
  viewBtn: {
    padding: '6px 14px',
    borderRadius: '6px',
    border: 'none',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff',
    fontSize: '12px',
    fontWeight: 500,
    cursor: 'pointer',
  },
  deleteBtn: {
    padding: '6px 14px',
    borderRadius: '6px',
    border: '1px solid rgba(239,68,68,0.3)',
    background: 'transparent',
    color: '#ef4444',
    fontSize: '12px',
    cursor: 'pointer',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: 'rgba(255,255,255,0.7)',
  },
  input: {
    padding: '12px 14px',
    borderRadius: '8px',
    border: '1px solid rgba(255,255,255,0.15)',
    background: 'rgba(255,255,255,0.05)',
    color: '#fff',
    fontSize: '14px',
    outline: 'none',
  },
};
