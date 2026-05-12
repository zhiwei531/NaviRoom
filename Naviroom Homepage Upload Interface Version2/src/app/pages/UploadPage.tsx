import { motion } from 'motion/react';
import { useState } from 'react';
import { ArrowLeft, Upload, Loader2, Sparkles, FileText, File } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { useNavigate } from 'react-router';
import { TopBar } from '../components/TopBar';
import logoImage from 'figma:asset/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';

interface RecommendationResult {
  room_id: string;
  final_score: number;
  semantic_score: number;
  behavior_score: number;
  reasons: string[];
  _source?: string;
}

type InputMode = 'text' | 'csv';

const SOURCE_LABEL: Record<string, string> = {
  text: 'Based on your text description',
  csv: 'Based on your uploaded CSV',
  dataset: 'Based on system dataset (DKU)',
};

export function UploadPage() {
  const navigate = useNavigate();
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [roomText, setRoomText] = useState('');
  const [query, setQuery] = useState('Need a quiet study room with screen for 4 people');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [recommendations, setRecommendations] = useState<RecommendationResult[]>([]);

  const handleCsvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setCsvFile(file);
    setMessage('');
    setError('');
    setRecommendations([]);
  };

  const handleSubmit = async () => {
    if (!query.trim()) {
      setError('Please describe what kind of room you need (search query)');
      return;
    }
    if (inputMode === 'text' && !roomText.trim()) {
      setError('Please describe the rooms you have, or switch to CSV upload mode');
      return;
    }
    if (inputMode === 'csv' && !csvFile) {
      setError('Please upload a CSV file, or switch to text description mode');
      return;
    }
    setError('');
    setMessage('');
    setLoading(true);
    setRecommendations([]);

    try {
      const formData = new FormData();
      formData.append('user_query', query.trim());
      if (inputMode === 'text') {
        formData.append('room_text', roomText.trim());
      } else if (csvFile) {
        formData.append('file', csvFile);
      }

      const res = await fetch('/recommend/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Request failed (${res.status})`);
      }

      const data = (await res.json()) as RecommendationResult[];
      setRecommendations(data);
      if (!data.length) {
        setMessage('No recommendations returned. Try adjusting your query or room descriptions.');
      } else {
        const src = data[0]?._source ?? '';
        setMessage(`${SOURCE_LABEL[src] ?? 'Recommendations ready'} — ${data.length} results`);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Top utility bar */}
      <TopBar />

      {/* Navigation */}
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="fixed left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100"
        style={{ top: '36px' }}
      >
        <div className="max-w-7xl mx-auto px-8 h-20 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 hover:opacity-70 transition-opacity"
          >
            <ArrowLeft className="w-5 h-5" />
            <img src={logoImage} alt="NaviRoom" className="h-10" />
          </button>
        </div>
      </motion.nav>

      {/* Main Content */}
      <div className="pt-40 pb-20 px-8">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h1 className="text-6xl tracking-tight mb-6">Find Your Room</h1>
            <p className="text-2xl text-gray-600">
              Describe what you need, optionally upload your own room data, and get instant recommendations
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="space-y-12"
          >

            {/* Step 1: Room data source */}
            <div>
              <p className="text-3xl mb-6">Step 1 — Provide room data</p>
              <p className="text-lg text-gray-500 mb-6">
                Tell us about the rooms you want to search in. Choose one method:
              </p>

              {/* Mode tabs */}
              <div className="flex gap-3 mb-8">
                <button
                  onClick={() => { setInputMode('text'); setCsvFile(null); setError(''); }}
                  className={`flex items-center gap-2 px-6 py-3 rounded-2xl text-base font-medium border-2 transition-all ${
                    inputMode === 'text'
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-200 text-gray-500 hover:border-gray-400'
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  Text description
                </button>
                <button
                  onClick={() => { setInputMode('csv'); setRoomText(''); setError(''); }}
                  className={`flex items-center gap-2 px-6 py-3 rounded-2xl text-base font-medium border-2 transition-all ${
                    inputMode === 'csv'
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-200 text-gray-500 hover:border-gray-400'
                  }`}
                >
                  <File className="w-4 h-4" />
                  CSV upload
                </button>
              </div>

              {/* Text mode */}
              {inputMode === 'text' && (
                <div>
                  <p className="text-base text-gray-500 mb-4">
                    Describe each room in plain English. Each line or paragraph is one room.
                    Example: <em>&quot;Room 301, floor 3, capacity 12, has projector and whiteboard, wheelchair accessible&quot;</em>
                  </p>
                  <Textarea
                    value={roomText}
                    onChange={(e) => setRoomText(e.target.value)}
                    placeholder={`Room 101, floor 1, capacity 8, has projector and whiteboard\nRoom 202, floor 2, capacity 20, lecture hall with microphone and recording equipment\nConf rm B203, 2F, max 12 pax, projector/whiteboard/vc, wheelchair access`}
                    className="min-h-[200px] text-base p-6 rounded-3xl border-2 border-gray-200 focus:border-blue-600 resize-none font-mono"
                  />
                  <p className="text-sm text-gray-400 mt-3">{roomText.length} characters</p>
                </div>
              )}

              {/* CSV mode */}
              {inputMode === 'csv' && (
                <div>
                  <p className="text-base text-gray-500 mb-4">
                    Upload a CSV file with room info (room_id, floor, capacity, description, etc.)
                  </p>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleCsvChange}
                    className="hidden"
                    id="csv-upload"
                  />
                  <label
                    htmlFor="csv-upload"
                    className="block border-2 border-dashed border-gray-200 rounded-3xl p-12 text-center cursor-pointer hover:border-blue-600 hover:bg-gray-50 transition-all duration-300"
                  >
                    <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                    <p className="text-xl text-gray-600 mb-2">
                      {csvFile ? csvFile.name : 'Click to upload CSV file'}
                    </p>
                    <p className="text-base text-gray-400">Supported: .csv (max 10 MB)</p>
                  </label>
                  {csvFile && (
                    <button
                      onClick={() => setCsvFile(null)}
                      className="mt-3 text-sm text-gray-400 hover:text-red-500 transition-colors"
                    >
                      Remove file
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Step 2: Search query */}
            <div>
              <p className="text-3xl mb-6">Step 2 — What are you looking for?</p>
              <p className="text-lg text-gray-500 mb-4">
                Describe your requirements in natural language.
              </p>
              <Textarea
                id="query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Need a quiet study room with projector for 4 people"
                className="min-h-[160px] text-xl p-8 rounded-3xl border-2 border-gray-200 focus:border-blue-600 resize-none"
              />
              <p className="text-lg text-gray-400 mt-4">
                {query.length} characters
              </p>
            </div>

            <div className="flex justify-center pt-4">
              <Button
                onClick={handleSubmit}
                disabled={loading || !query.trim()}
                size="lg"
                className="h-16 px-12 text-xl rounded-full"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 w-6 h-6 animate-spin" />
                    Finding rooms...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 w-6 h-6" />
                    Get Recommendations
                  </>
                )}
              </Button>
            </div>

            {error && <p className="text-red-500 text-lg text-center">{error}</p>}
            {message && <p className="text-green-600 text-lg text-center">{message}</p>}

            {recommendations.length > 0 && (
              <div className="space-y-4 mt-8">
                <h3 className="text-3xl mb-6">Top Recommendations</h3>
                {recommendations.map((item, idx) => (
                  <div key={`${item.room_id}-${idx}`} className="border border-gray-200 rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-2xl font-medium">#{idx + 1} &nbsp; {item.room_id}</p>
                      <p className="text-lg text-gray-500">
                        Score: {typeof item.final_score === 'number' ? item.final_score.toFixed(3) : item.final_score}
                      </p>
                    </div>
                    {item.reasons && item.reasons.length > 0 && (
                      <ul className="list-disc pl-6 text-gray-700 space-y-1 text-base">
                        {item.reasons.map((reason, i) => (
                          <li key={i}>{reason}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}