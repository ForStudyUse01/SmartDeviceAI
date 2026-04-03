import { useRef, useState } from 'react'
import { analyzeBatchImages, analyzeHybridImage } from '../lib/api'

export function HybridAIPage() {
  const [selectedFiles, setSelectedFiles] = useState([])
  const [previews, setPreviews] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [confThreshold, setConfThreshold] = useState(0.25)
  const imgRefs = useRef({})

  function handleFileChange(event) {
    const files = Array.from(event.target.files || [])
    if (files.length > 0) {
      const newPreviews = files.map(file => URL.createObjectURL(file))
      setSelectedFiles(files)
      setPreviews(newPreviews)
      setResults(null)
      setError('')
    }
  }

  async function handleAnalyze() {
    if (selectedFiles.length === 0) return
    setLoading(true)
    setError('')
    setResults(null)

    try {
      let data
      if (selectedFiles.length === 1) {
        // Single image analysis
        data = await analyzeHybridImage(selectedFiles[0], Math.min(confThreshold, 0.9))
        // Wrap single result in format consistent with batch
        setResults({
          status: data.status,
          total_images: 1,
          successful: data.status === 'success' ? 1 : 0,
          failed: data.status === 'error' ? 1 : 0,
          total_objects_detected: data.num_detections || 0,
          results: [data],
        })
      } else {
        // Batch analysis
        data = await analyzeBatchImages(selectedFiles, Math.min(confThreshold, 0.9))
        setResults(data)
      }
    } catch (err) {
      setError(err.message || 'Analysis failed.')
    } finally {
      setLoading(false)
    }
  }

  function renderBoundingBoxes(imageIndex) {
    if (!results || !results.results || !results.results[imageIndex]) return null

    const imageResult = results.results[imageIndex]
    if (!imageResult.detected_objects || imageResult.detected_objects.length === 0) return null

    const imgRef = imgRefs.current[imageIndex]
    if (!imgRef) return null

    const { naturalWidth, naturalHeight, width, height } = imgRef
    const scaleX = width / naturalWidth
    const scaleY = height / naturalHeight

    return imageResult.detected_objects.map((obj, i) => {
      const [x1, y1, x2, y2] = obj.box
      const left = x1 * scaleX
      const top = y1 * scaleY
      const w = (x2 - x1) * scaleX
      const h = (y2 - y1) * scaleY

      const ecoColor = obj.eco_score > 70 ? '#10b981' : obj.eco_score > 40 ? '#f59e0b' : '#ef4444'

      return (
        <div
          key={i}
          style={{
            position: 'absolute',
            left,
            top,
            width: w,
            height: h,
            border: `3px solid ${ecoColor}`,
            backgroundColor: `${ecoColor}33`,
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: '-24px',
              left: '-3px',
              backgroundColor: ecoColor,
              color: 'white',
              padding: '2px 6px',
              fontSize: '12px',
              fontWeight: 'bold',
              whiteSpace: 'nowrap',
              borderRadius: '2px',
            }}
          >
            {obj.yolo_label} ({Math.round(obj.yolo_confidence)}%)
          </div>
        </div>
      )
    })
  }

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas">
        <span className="eyebrow eyebrow-indigo">Advanced AI Pipeline</span>
        <h1 className="dashboard-title">E-waste Detection & Analysis</h1>
        <p className="dashboard-subtitle">
          Upload images to identify electronic waste objects. YOLO detects components and our VLM analyzes their condition with recycling recommendations.
        </p>
      </section>

      <section className="content-grid" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)' }}>
        <div className="glass-panel panel-hover saas-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h2 className="panel-title">1. Image Upload & Settings</h2>

          <div className="upload-dropzone manual-upload-dropzone" style={{ minHeight: '120px' }}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg"
              onChange={handleFileChange}
              multiple
            />
            <span className="upload-meta">
              {selectedFiles.length > 0
                ? `${selectedFiles.length} image(s) selected`
                : 'Click to select images (up to 10)'}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.9rem', fontWeight: 500 }}>
              YOLO Confidence Threshold: {confThreshold.toFixed(2)}
            </label>
            <input
              type="range"
              min="0"
              max="0.9"
              step="0.05"
              value={confThreshold}
              onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Lower = more detections, Higher = fewer false positives
            </span>
          </div>

          <button
            className="primary-button"
            onClick={handleAnalyze}
            disabled={selectedFiles.length === 0 || loading}
          >
            {loading ? 'Analyzing with YOLO + VLM...' : `Run Analysis (${selectedFiles.length} image${selectedFiles.length !== 1 ? 's' : ''})`}
          </button>

          {error && <div className="error-banner">{error}</div>}

          {previews.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
              {previews.map((previewUrl, idx) => (
                <div key={idx} style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', border: '2px solid var(--border)' }}>
                  <img
                    ref={(el) => (imgRefs.current[idx] = el)}
                    src={previewUrl}
                    alt={`Preview ${idx}`}
                    style={{ width: '100%', height: 'auto', display: 'block' }}
                    onLoad={() => {
                      setResults((prev) => (prev ? { ...prev } : prev))
                    }}
                  />
                  {results && renderBoundingBoxes(idx)}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">2. Analysis Results</h2>
          <p className="panel-subtitle" style={{ marginBottom: '1.5rem' }}>
            Detailed breakdown of detected components and their recycling potential.
          </p>

          {!results && !loading && (
            <div className="empty-state">
              Upload images and run analysis to see detailed component breakdowns.
            </div>
          )}

          {loading && (
            <div className="empty-state" style={{ color: 'var(--primary)', fontWeight: 500 }}>
              Running YOLOv8 detection and VLM analysis...
            </div>
          )}

          {results && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Overall Stats */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                gap: '1rem',
                padding: '1rem',
                backgroundColor: 'var(--panel-bg)',
                borderRadius: '8px',
                border: '1px solid var(--border)'
              }}>
                <div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Total Images</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{results.total_images}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Objects Found</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{results.total_objects_detected}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Success Rate</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
                    {results.total_images > 0 ? Math.round((results.successful / results.total_images) * 100) : 0}%
                  </div>
                </div>
              </div>

              {/* Per-Image Results */}
              {results.results && results.results.map((imageResult, imgIdx) => (
                <div key={imgIdx} style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Image {imgIdx + 1}: {imageResult.image_name}</h3>

                  {imageResult.error_message && (
                    <div className="error-banner" style={{ marginBottom: '1rem' }}>
                      {imageResult.error_message}
                    </div>
                  )}

                  {imageResult.detected_objects && imageResult.detected_objects.length === 0 && (
                    <div className="empty-state" style={{ color: 'var(--text-secondary)' }}>
                      No supported electronic devices detected.
                    </div>
                  )}

                  {imageResult.detected_objects && imageResult.detected_objects.map((obj, idx) => (
                    <div key={idx} style={{
                      padding: '1rem',
                      backgroundColor: 'var(--panel-bg)',
                      borderRadius: '8px',
                      border: '1px solid var(--border)',
                      marginBottom: '0.75rem'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <div>
                          <h4 style={{ margin: '0 0 0.25rem 0' }}>{obj.vlm_object}</h4>
                          <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            YOLO: {obj.yolo_label} ({Math.round(obj.yolo_confidence)}%)
                          </div>
                        </div>
                        <div style={{
                          backgroundColor: obj.eco_score > 70 ? '#10b98122' : obj.eco_score > 40 ? '#f59e0b22' : '#ef444422',
                          color: obj.eco_score > 70 ? '#10b981' : obj.eco_score > 40 ? '#f59e0b' : '#ef4444',
                          padding: '6px 12px',
                          borderRadius: '6px',
                          fontSize: '0.9rem',
                          fontWeight: 600,
                          minWidth: 'max-content'
                        }}>
                          Eco Score: {obj.eco_score}/100
                        </div>
                      </div>

                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '1rem',
                        paddingTop: '0.75rem',
                        borderTop: '1px solid var(--border)'
                      }}>
                        <div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>Condition</div>
                          <div style={{ fontWeight: 500 }}>{obj.condition}</div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>Recommendation</div>
                          <div style={{ fontSize: '0.95rem', lineHeight: 1.4 }}>{obj.suggestion}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
