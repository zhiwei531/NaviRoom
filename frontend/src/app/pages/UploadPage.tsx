import { motion } from 'motion/react';
import { useState } from 'react';
import { ArrowLeft, Upload, Sparkles, FileText, Loader2, MapPin } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { useNavigate } from 'react-router';
import logoImage from '../../assets/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';

// 后端返回的推荐结果类型
interface RecommendationResult {
  room_id: string;
  final_score: number;
  semantic_score: number;
  behavior_score: number;
  reasons: string[];
  _source?: string;
}

export function UploadPage() {
  const navigate = useNavigate();

  // 表单状态
  const [userQuery, setUserQuery] = useState('');
  const [roomText, setRoomText] = useState('');
  const [file, setFile] = useState<File | null>(null);

  // 请求状态
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RecommendationResult[]>([]);
  const [error, setError] = useState('');
  const [source, setSource] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null;
    setFile(selected);
    setResults([]);
    setError('');
  };

  const handleSubmit = async () => {
    if (!userQuery.trim() && !file && !roomText.trim()) return;

    setLoading(true);
    setError('');
    setResults([]);

    try {
      const formData = new FormData();
      formData.append('user_query', userQuery);
      formData.append('requirements', '{}');

      if (roomText.trim()) {
        formData.append('room_text', roomText);
      }
      if (file) {
        formData.append('file', file);
      }

      const response = await fetch('/recommend/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `服务器错误 (${response.status})`);
      }

      const data: RecommendationResult[] = await response.json();
      setResults(data);
      setSource(data[0]?._source || '');
    } catch (err: any) {
      setError(err.message || '请求失败，请检查后端服务是否运行');
    } finally {
      setLoading(false);
    }
  };

  const scorePercent = (score: number) => `${Math.round(score * 100)}%`;

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100"
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
      <div className="pt-32 pb-20 px-8">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h1 className="text-6xl tracking-tight mb-6">Find Your Room</h1>
            <p className="text-2xl text-gray-600">
              Describe what you need — AI will recommend the best room
            </p>
          </motion.div>

          {/* Input Form */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="space-y-8"
          >
            {/* User Query */}
            <div>
              <label htmlFor="query" className="block text-3xl mb-4">
                What do you need?
              </label>
              <Textarea
                id="query"
                value={userQuery}
                onChange={(e) => setUserQuery(e.target.value)}
                placeholder='e.g. "I need a quiet study room for 3 people with a whiteboard and screen for an online interview"'
                className="min-h-[120px] text-xl p-8 rounded-3xl border-2 border-gray-200 focus:border-blue-600 resize-none"
              />
              <p className="text-lg text-gray-400 mt-2">
                Describe your requirements in natural language
              </p>
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-3xl mb-4">Room Data</label>
              <div className="relative">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileChange}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className={`block border-2 rounded-3xl p-12 text-center cursor-pointer transition-all duration-300 ${
                    file
                      ? 'border-blue-600 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-600 hover:bg-gray-50'
                  }`}
                >
                  {file ? (
                    <>
                      <FileText className="w-12 h-12 mx-auto mb-3 text-blue-600" />
                      <p className="text-xl text-blue-600 font-medium">{file.name}</p>
                      <p className="text-base text-gray-400 mt-1">
                        {(file.size / 1024).toFixed(1)} KB
                      </p>
                    </>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                      <p className="text-xl text-gray-600 mb-1">
                        Upload CSV or Excel file with room data
                      </p>
                      <p className="text-base text-gray-400">
                        Optional — leave empty to use system dataset
                      </p>
                    </>
                  )}
                </label>
              </div>
            </div>

            {/* Room Text (alternative to file) */}
            <div>
              <label htmlFor="room-text" className="block text-3xl mb-4">
                Or describe rooms directly
              </label>
              <Textarea
                id="room-text"
                value={roomText}
                onChange={(e) => setRoomText(e.target.value)}
                placeholder='e.g. "Room A: capacity=4, has_screen=yes, has_whiteboard=yes, study room on floor 3"'
                className="min-h-[120px] text-xl p-8 rounded-3xl border-2 border-gray-200 focus:border-blue-600 resize-none"
              />
              <p className="text-lg text-gray-400 mt-2">
                Describe rooms in free text — AI will parse them automatically
              </p>
            </div>

            {/* Submit Button */}
            <div className="flex justify-center pt-4">
              <Button
                onClick={handleSubmit}
                disabled={loading || (!userQuery.trim() && !file && !roomText.trim())}
                size="lg"
                className="h-16 px-12 text-xl rounded-full gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-6 h-6" />
                    Get Recommendations
                  </>
                )}
              </Button>
            </div>

            {/* Error message */}
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center"
              >
                <p className="text-red-600 text-lg">{error}</p>
              </motion.div>
            )}
          </motion.div>

          {/* Results */}
          {results.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mt-20"
            >
              <div className="text-center mb-10">
                <h2 className="text-4xl tracking-tight mb-2">
                  Top {results.length} Recommendations
                </h2>
                {source && (
                  <p className="text-lg text-gray-400">
                    Data source: {source}
                  </p>
                )}
              </div>

              <div className="space-y-6">
                {results.map((room, index) => (
                  <motion.div
                    key={room.room_id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <Card className="rounded-3xl border-2 hover:border-blue-300 transition-colors">
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-lg ${
                              index === 0 ? 'bg-yellow-500' :
                              index === 1 ? 'bg-gray-400' :
                              index === 2 ? 'bg-amber-700' : 'bg-gray-300'
                            }`}>
                              {index + 1}
                            </div>
                            <div>
                              <CardTitle className="text-2xl flex items-center gap-2">
                                <MapPin className="w-5 h-5 text-blue-600" />
                                {room.room_id}
                              </CardTitle>
                              <CardDescription className="text-base">
                                Match score: {scorePercent(room.final_score)}
                              </CardDescription>
                            </div>
                          </div>
                          <Badge variant="secondary" className="text-lg px-4 py-2 rounded-full">
                            {scorePercent(room.final_score)}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent>
                        {/* Score bars */}
                        <div className="grid grid-cols-3 gap-4 mb-4">
                          <div>
                            <p className="text-sm text-gray-500 mb-1">Semantic</p>
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-blue-500 rounded-full transition-all"
                                style={{ width: scorePercent(room.semantic_score) }}
                              />
                            </div>
                          </div>
                          <div>
                            <p className="text-sm text-gray-500 mb-1">Behavior</p>
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-green-500 rounded-full transition-all"
                                style={{ width: scorePercent(room.behavior_score) }}
                              />
                            </div>
                          </div>
                          <div>
                            <p className="text-sm text-gray-500 mb-1">Final</p>
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-purple-500 rounded-full transition-all"
                                style={{ width: scorePercent(room.final_score) }}
                              />
                            </div>
                          </div>
                        </div>

                        {/* Reasons */}
                        {room.reasons.length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {room.reasons.map((reason, i) => (
                              <Badge key={i} variant="outline" className="text-sm rounded-full">
                                {reason}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
