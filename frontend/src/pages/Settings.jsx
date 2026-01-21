import React, { useState, useEffect } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { settingsAPI } from '../lib/api';
import { Settings as SettingsIcon, Key, Globe, Cpu, Save, Loader2, Eye, EyeOff, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const AI_MODELS = [
  { value: 'openai/gpt-4o', label: 'GPT-4o (Recommended)' },
  { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini (Faster)' },
  { value: 'openai/gpt-4-turbo', label: 'GPT-4 Turbo' },
  { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
  { value: 'anthropic/claude-3-opus', label: 'Claude 3 Opus' },
  { value: 'google/gemini-pro-1.5', label: 'Gemini Pro 1.5' },
  { value: 'meta-llama/llama-3-70b-instruct', label: 'Llama 3 70B' },
];

export const Settings = () => {
  const [settings, setSettings] = useState({
    openrouter_api_key: '',
    model_name: 'openai/gpt-4o-mini',
    language: 'en',
    has_api_key: false,
    openrouter_api_key_masked: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await settingsAPI.get();
      setSettings(res.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updateData = {
        model_name: settings.model_name,
        language: settings.language
      };
      
      if (newApiKey) {
        updateData.openrouter_api_key = newApiKey;
      }
      
      await settingsAPI.update(updateData);
      toast.success('Settings saved');
      setNewApiKey('');
      loadSettings();
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="settings-page">
      <TopBar title="Settings" subtitle="Configure your workspace" />
      
      <div className="p-8 max-w-2xl">
        <div className="space-y-6">
          {/* API Configuration */}
          <Card className="border-slate-100 shadow-soft">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <Key className="w-5 h-5 text-indigo-500" />
                OpenRouter API
              </CardTitle>
              <CardDescription>
                Configure your OpenRouter API key for AI features
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {settings.has_api_key && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-green-50 text-green-700 text-sm">
                  <CheckCircle className="w-4 h-4" />
                  API key configured: {settings.openrouter_api_key_masked}
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="apiKey">{settings.has_api_key ? 'Update API Key' : 'API Key'}</Label>
                <div className="relative">
                  <Input
                    id="apiKey"
                    type={showApiKey ? 'text' : 'password'}
                    value={newApiKey}
                    onChange={(e) => setNewApiKey(e.target.value)}
                    placeholder={settings.has_api_key ? 'Enter new key to update' : 'sk-or-...'}
                    className="pr-10"
                    data-testid="api-key-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-slate-500">
                  Get your API key from{' '}
                  <a 
                    href="https://openrouter.ai/keys" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-indigo-600 hover:underline"
                  >
                    openrouter.ai/keys
                  </a>
                </p>
              </div>
            </CardContent>
          </Card>

          {/* AI Model Selection */}
          <Card className="border-slate-100 shadow-soft">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <Cpu className="w-5 h-5 text-indigo-500" />
                AI Model
              </CardTitle>
              <CardDescription>
                Select the AI model for analysis and generation
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Select
                value={settings.model_name}
                onValueChange={(v) => setSettings(prev => ({ ...prev, model_name: v }))}
              >
                <SelectTrigger data-testid="model-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AI_MODELS.map(model => (
                    <SelectItem key={model.value} value={model.value}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Language Settings */}
          <Card className="border-slate-100 shadow-soft">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <Globe className="w-5 h-5 text-indigo-500" />
                Language
              </CardTitle>
              <CardDescription>
                Set the language for AI-generated content
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Select
                value={settings.language}
                onValueChange={(v) => setSettings(prev => ({ ...prev, language: v }))}
              >
                <SelectTrigger data-testid="language-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="id">Indonesian (Bahasa Indonesia)</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Save Button */}
          <Button
            onClick={handleSave}
            disabled={saving}
            className="w-full bg-indigo-500 hover:bg-indigo-600 text-white rounded-full py-6"
            data-testid="save-settings-btn"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Settings
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
