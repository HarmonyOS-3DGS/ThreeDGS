import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { sceneApi } from '../api';
import type { Scene } from '../types';

// We need to dynamically import the GaussianSplats3D library
// since it may not be available at build time in all environments

declare global {
  interface Window {
    GaussianSplats3D?: any;
    THREE?: any;
  }
}

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  
  const [scene, setScene] = useState<Scene | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [viewerReady, setViewerReady] = useState(false);
  const [viewerMode, setViewerMode] = useState<'gs3d' | 'fallback'>('gs3d');

  // Load scene data
  useEffect(() => {
    if (!id) return;
    
    const loadScene = async () => {
      try {
        const data = await sceneApi.get(parseInt(id));
        setScene(data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load scene');
      } finally {
        setLoading(false);
      }
    };
    
    loadScene();
  }, [id]);

  // Initialize 3D Viewer
  useEffect(() => {
    if (!scene || !containerRef.current) return;
    
    const initViewer = async () => {
      try {
        // Try to load the GaussianSplats3D library dynamically
        const gs3dModule = await import('@mkkellogg/gaussian-splats-3d');
        const THREE = await import('three');
        
        const container = containerRef.current;
        if (!container) return;
        
        // Clear previous content
        container.innerHTML = '';
        
        // Get container dimensions
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        // Create renderer
        const renderer = new THREE.WebGLRenderer({ antialias: false });
        renderer.setSize(width, height);
        container.appendChild(renderer.domElement);
        
        // Create camera
        const camera = new THREE.PerspectiveCamera(65, width / height, 0.1, 500);
        camera.position.set(-1, -4, 6);
        camera.up.set(0, -1, -0.6).normalize();
        camera.lookAt(0, 4, -0);
        
        // Create viewer
        const viewer = new gs3dModule.Viewer({
          selfDrivenMode: true,
          renderer: renderer,
          camera: camera,
          useBuiltInControls: true,
          gpuAcceleratedSort: true,
          enableSIMDInSort: true,
          sharedMemoryForWorkers: true,
          integerBasedSort: true,
          halfPrecisionCovariancesOnGPU: true,
          sceneRevealMode: gs3dModule.SceneRevealMode.Instant,
          antialiased: false,
          sphericalHarmonicsDegree: scene.sh_degree || 0,
        });
        
        viewerRef.current = viewer;
        
        // Load the scene file
        const sceneUrl = sceneApi.getRawUrl(scene.id);
        
        await viewer.addSplatScene(sceneUrl, {
          format: scene.file_format as any,
        });
        
        setViewerReady(true);
        
      } catch (err) {
        console.warn('GaussianSplats3D viewer failed, using fallback:', err);
        setViewerMode('fallback');
        initFallbackViewer();
      }
    };
    
    const initFallbackViewer = () => {
      // Fallback: Show scene info and provide download link
      setLoading(false);
    };
    
    initViewer();
    
    // Cleanup
    return () => {
      if (viewerRef.current) {
        try {
          viewerRef.current.dispose();
        } catch (e) {
          // Ignore cleanup errors
        }
      }
    };
  }, [scene]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (viewerRef.current) {
        // The viewer should handle resize automatically in self-driven mode
      }
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loading}>Loading scene...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.error}>
          <p>{error}</p>
          <button onClick={() => navigate('/dashboard')} style={styles.backBtn}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerContent}>
          <button onClick={() => navigate('/dashboard')} style={styles.backBtn}>
            &larr; Back
          </button>
          <h1 style={styles.title}>{scene?.name}</h1>
          <div style={styles.sceneInfo}>
            {scene?.num_gaussians && (
              <span style={styles.infoBadge}>
                {scene.num_gaussians.toLocaleString()} Gaussians
              </span>
            )}
            <span style={styles.infoBadge}>
              {scene?.file_format.toUpperCase()}
            </span>
          </div>
        </div>
      </header>

      {/* Viewer Container */}
      <div style={styles.viewerWrapper}>
        {viewerMode === 'gs3d' ? (
          <div ref={containerRef} style={styles.viewerContainer} />
        ) : (
          <FallbackViewer scene={scene!} />
        )}
        
        {/* Controls overlay */}
        {viewerReady && (
          <div style={styles.controls}>
            <div style={styles.controlGroup}>
              <span style={styles.controlLabel}>Controls:</span>
              <span style={styles.controlHint}>Left Click + Drag = Orbit</span>
              <span style={styles.controlHint}>Right Click + Drag = Pan</span>
              <span style={styles.controlHint}>Scroll = Zoom</span>
            </div>
            <a
              href={sceneApi.getDownloadUrl(scene!.id)}
              download
              style={styles.downloadLink}
            >
              Download File
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// Fallback viewer when WebGL/3D library isn't available
function FallbackViewer({ scene }: { scene: Scene }) {
  return (
    <div style={fallbackStyles.container}>
      <div style={fallbackStyles.card}>
        <h2 style={fallbackStyles.title}>3D Viewer</h2>
        <p style={fallbackStyles.description}>
          The interactive 3D viewer requires WebGL support and the GaussianSplats3D library.
          You can still download the scene file to view it locally.
        </p>
        
        <div style={fallbackStyles.meta}>
          <div style={fallbackStyles.metaItem}>
            <span style={fallbackStyles.metaLabel}>Scene Name</span>
            <span style={fallbackStyles.metaValue}>{scene.name}</span>
          </div>
          <div style={fallbackStyles.metaItem}>
            <span style={fallbackStyles.metaLabel}>File Format</span>
            <span style={fallbackStyles.metaValue}>{scene.file_format.toUpperCase()}</span>
          </div>
          <div style={fallbackStyles.metaItem}>
            <span style={fallbackStyles.metaLabel}>File Size</span>
            <span style={fallbackStyles.metaValue}>
              {(scene.file_size / 1024 / 1024).toFixed(1)} MB
            </span>
          </div>
          <div style={fallbackStyles.metaItem}>
            <span style={fallbackStyles.metaLabel}>Gaussians</span>
            <span style={fallbackStyles.metaValue}>
              {scene.num_gaussians?.toLocaleString() || 'N/A'}
            </span>
          </div>
          {scene.scene_scale && (
            <div style={fallbackStyles.metaItem}>
              <span style={fallbackStyles.metaLabel}>Scene Scale</span>
              <span style={fallbackStyles.metaValue}>{scene.scene_scale.toFixed(4)}</span>
            </div>
          )}
          <div style={fallbackStyles.metaItem}>
            <span style={fallbackStyles.metaLabel}>SH Degree</span>
            <span style={fallbackStyles.metaValue}>{scene.sh_degree}</span>
          </div>
        </div>
        
        <a
          href={sceneApi.getDownloadUrl(scene.id)}
          download
          style={fallbackStyles.downloadBtn}
        >
          Download {scene.filename}
        </a>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a0f',
  },
  header: {
    background: 'rgba(255,255,255,0.03)',
    borderBottom: '1px solid rgba(255,255,255,0.08)',
    padding: '0 20px',
    flexShrink: 0,
  },
  headerContent: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '56px',
  },
  backBtn: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid rgba(255,255,255,0.2)',
    background: 'transparent',
    color: '#fff',
    fontSize: '13px',
    cursor: 'pointer',
  },
  title: {
    fontSize: '16px',
    fontWeight: 600,
    color: '#fff',
    margin: 0,
    flex: 1,
    textAlign: 'center',
  },
  sceneInfo: {
    display: 'flex',
    gap: '8px',
  },
  infoBadge: {
    padding: '4px 10px',
    borderRadius: '12px',
    background: 'rgba(102,126,234,0.15)',
    color: '#667eea',
    fontSize: '12px',
    fontWeight: 500,
  },
  viewerWrapper: {
    flex: 1,
    position: 'relative',
    overflow: 'hidden',
  },
  viewerContainer: {
    width: '100%',
    height: '100%',
  },
  controls: {
    position: 'absolute',
    bottom: '20px',
    left: '20px',
    right: '20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: 'rgba(0,0,0,0.7)',
    backdropFilter: 'blur(10px)',
    padding: '12px 20px',
    borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.1)',
  },
  controlGroup: {
    display: 'flex',
    gap: '16px',
    alignItems: 'center',
  },
  controlLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#fff',
  },
  controlHint: {
    fontSize: '12px',
    color: 'rgba(255,255,255,0.5)',
  },
  downloadLink: {
    padding: '8px 16px',
    borderRadius: '6px',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff',
    fontSize: '12px',
    fontWeight: 500,
    textDecoration: 'none',
  },
  loadingContainer: {
    height: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#0a0a0f',
  },
  loading: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: '16px',
  },
  error: {
    textAlign: 'center',
    color: '#ef4444',
  },
};

const fallbackStyles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#0a0a0f',
  },
  card: {
    background: 'rgba(255,255,255,0.05)',
    borderRadius: '16px',
    padding: '40px',
    maxWidth: '500px',
    width: '90%',
    border: '1px solid rgba(255,255,255,0.1)',
  },
  title: {
    fontSize: '24px',
    fontWeight: 600,
    color: '#fff',
    marginBottom: '12px',
    textAlign: 'center',
  },
  description: {
    fontSize: '14px',
    color: 'rgba(255,255,255,0.5)',
    textAlign: 'center',
    marginBottom: '24px',
    lineHeight: 1.6,
  },
  meta: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    marginBottom: '24px',
  },
  metaItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  metaLabel: {
    fontSize: '11px',
    color: 'rgba(255,255,255,0.4)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  metaValue: {
    fontSize: '14px',
    color: '#fff',
    fontWeight: 500,
  },
  downloadBtn: {
    display: 'block',
    width: '100%',
    padding: '14px',
    borderRadius: '8px',
    border: 'none',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff',
    fontSize: '15px',
    fontWeight: 600,
    textAlign: 'center',
    textDecoration: 'none',
    cursor: 'pointer',
  },
};
