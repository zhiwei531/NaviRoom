import { useState } from 'react';
import { Card } from './ui/card';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Button } from './ui/button';
import { Save } from 'lucide-react';

interface DescriptionEditorProps {
  title: string;
  placeholder?: string;
  maxLength?: number;
}

export function DescriptionEditor({
  title,
  placeholder = 'Enter description...',
  maxLength = 1000,
}: DescriptionEditorProps) {
  const [description, setDescription] = useState('');

  const handleSave = () => {
    console.log('Saving description:', description);
    // Save logic would go here
  };

  return (
    <Card className="p-6">
      <Label htmlFor="description" className="mb-2 block">
        {title}
      </Label>
      <Textarea
        id="description"
        placeholder={placeholder}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        maxLength={maxLength}
        className="min-h-[200px] mb-2"
      />
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500">
          {description.length} / {maxLength} characters
        </span>
        <Button onClick={handleSave}>
          <Save className="w-4 h-4 mr-2" />
          Save Description
        </Button>
      </div>
    </Card>
  );
}
