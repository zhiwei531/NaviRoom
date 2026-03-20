import { motion } from 'motion/react';
import { useState } from 'react';
import { ArrowLeft, Upload, Check } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { useNavigate } from 'react-router';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import logoImage from '../../assets/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';

export function UploadPage() {
  const navigate = useNavigate();
  const [description, setDescription] = useState('');
  const [images, setImages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setImages((prev) => [...prev, ...files]);

    files.forEach((file) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreviews((prev) => [...prev, reader.result as string]);
      };
      reader.readAsDataURL(file);
    });
  };

  const handleSubmit = () => {
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      setDescription('');
      setImages([]);
      setPreviews([]);
    }, 3000);
  };

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
            <h1 className="text-6xl tracking-tight mb-6">Upload your space</h1>
            <p className="text-2xl text-gray-600">
              Share your property details with the world
            </p>
          </motion.div>

          {/* Upload Form */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="space-y-12"
          >
            {/* Image Upload */}
            <div>
              <label className="block text-3xl mb-6">Photos</label>
              <div className="relative">
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                  id="image-upload"
                />
                <label
                  htmlFor="image-upload"
                  className="block border-2 border-gray-200 rounded-3xl p-16 text-center cursor-pointer hover:border-blue-600 hover:bg-gray-50 transition-all duration-300"
                >
                  <Upload className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                  <p className="text-2xl text-gray-600 mb-2">
                    Click to upload images
                  </p>
                  <p className="text-lg text-gray-400">or drag and drop</p>
                </label>
              </div>

              {/* Image Previews */}
              {previews.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8"
                >
                  {previews.map((preview, index) => (
                    <div
                      key={index}
                      className="aspect-square rounded-2xl overflow-hidden"
                    >
                      <img
                        src={preview}
                        alt={`Preview ${index + 1}`}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  ))}
                </motion.div>
              )}
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-3xl mb-6">
                Description
              </label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Tell us about your space. What makes it special? What amenities do you offer?"
                className="min-h-[300px] text-xl p-8 rounded-3xl border-2 border-gray-200 focus:border-blue-600 resize-none"
              />
              <p className="text-lg text-gray-400 mt-4">
                {description.length} characters
              </p>
            </div>

            {/* Submit Button */}
            <div className="flex justify-center pt-8">
              <Button
                onClick={handleSubmit}
                disabled={!description && images.length === 0}
                size="lg"
                className="h-16 px-12 text-xl rounded-full"
              >
                {submitted ? (
                  <>
                    <Check className="mr-2 w-6 h-6" />
                    Uploaded!
                  </>
                ) : (
                  'Publish'
                )}
              </Button>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Success Animation */}
      {submitted && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50"
        >
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-white rounded-3xl p-12 text-center shadow-2xl"
          >
            <div className="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-6">
              <Check className="w-10 h-10 text-white" />
            </div>
            <h3 className="text-4xl mb-2">Success!</h3>
            <p className="text-xl text-gray-600">
              Your content has been uploaded
            </p>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}