import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Slider } from '../components/ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { jobsAPI } from '../lib/api';
import { Sparkles, Save, Loader2, ArrowLeft, Trash2, Plus, Users, Target, Wrench, FileText, PenLine } from 'lucide-react';
import { toast } from 'sonner';

export const JobEdit = () => {
  const { id } = useParams();
  const isNew = id === 'new';
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatingPlaybook, setGeneratingPlaybook] = useState(false);
  const [deleting, setDeleting] = useState(false);
  
  const [form, setForm] = useState({
    title: '',
    description: '',
    requirements: '',
    location: '',
    employment_type: 'full-time',
    salary_range: '',
    playbook: null
  });

  useEffect(() => {
    if (!isNew) {
      loadJob();
    }
  }, [id, isNew]);

  const loadJob = async () => {
    try {
      const res = await jobsAPI.get(id);
      setForm(res.data);
    } catch (error) {
      toast.error('Failed to load job');
      navigate('/jobs');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!form.title.trim()) {
      toast.error('Job title is required');
      return;
    }
    if (!form.description.trim()) {
      toast.error('Job description is required');
      return;
    }

    setSaving(true);
    try {
      if (isNew) {
        const res = await jobsAPI.create(form);
        toast.success('Job created');
        navigate(`/jobs/${res.data.id}`);
      } else {
        await jobsAPI.update(id, form);
        toast.success('Job updated');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this job?')) return;
    
    setDeleting(true);
    try {
      await jobsAPI.delete(id);
      toast.success('Job deleted');
      navigate('/jobs');
    } catch (error) {
      toast.error('Failed to delete job');
    } finally {
      setDeleting(false);
    }
  };

  const handleGenerateDescription = async () => {
    if (!form.title.trim()) {
      toast.error('Enter a job title first');
      return;
    }

    setGenerating(true);
    try {
      const res = await jobsAPI.generateDescription(form.title, '');
      setForm(prev => ({
        ...prev,
        description: res.data.description || prev.description,
        requirements: res.data.requirements || prev.requirements
      }));
      toast.success('Description generated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate description');
    } finally {
      setGenerating(false);
    }
  };

  const handleGeneratePlaybook = async () => {
    if (isNew) {
      toast.error('Save the job first before generating playbook');
      return;
    }

    setGeneratingPlaybook(true);
    try {
      const res = await jobsAPI.generatePlaybook(id);
      setForm(prev => ({ ...prev, playbook: res.data.playbook }));
      toast.success('Playbook generated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate playbook');
    } finally {
      setGeneratingPlaybook(false);
    }
  };

  const updatePlaybookItem = (category, index, field, value) => {
    setForm(prev => ({
      ...prev,
      playbook: {
        ...prev.playbook,
        [category]: prev.playbook[category].map((item, i) =>
          i === index ? { ...item, [field]: value } : item
        )
      }
    }));
  };

  const addPlaybookItem = (category) => {
    setForm(prev => ({
      ...prev,
      playbook: {
        ...prev.playbook,
        [category]: [...(prev.playbook?.[category] || []), { id: crypto.randomUUID(), name: '', description: '', weight: 0 }]
      }
    }));
  };

  const removePlaybookItem = (category, index) => {
    setForm(prev => ({
      ...prev,
      playbook: {
        ...prev.playbook,
        [category]: prev.playbook[category].filter((_, i) => i !== index)
      }
    }));
  };

  const getCategoryWeight = (category) => {
    return (form.playbook?.[category] || []).reduce((sum, item) => sum + (item.weight || 0), 0);
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'character': return Users;
      case 'requirement': return Target;
      case 'skill': return Wrench;
      default: return Users;
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
    <div className="min-h-screen" data-testid="job-edit-page">
      <TopBar 
        title={isNew ? 'Create Job' : 'Edit Job'} 
        subtitle={form.title || 'New position'}
      />
      
      <div className="p-8 max-w-4xl">
        <Button
          variant="ghost"
          onClick={() => navigate('/jobs')}
          className="mb-6"
          data-testid="back-btn"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Jobs
        </Button>

        <Tabs defaultValue="details" className="space-y-6">
          <TabsList className="bg-slate-100 p-1 rounded-full">
            <TabsTrigger value="details" className="rounded-full px-6">Job Details</TabsTrigger>
            <TabsTrigger value="playbook" className="rounded-full px-6">Evaluation Playbook</TabsTrigger>
          </TabsList>

          {/* Job Details Tab */}
          <TabsContent value="details" className="space-y-6 animate-fade-in">
            <Card className="border-slate-100 shadow-soft">
              <CardHeader>
                <CardTitle className="font-heading">Job Information</CardTitle>
                <CardDescription>Basic details about the position</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Job Title *</Label>
                    <Input
                      id="title"
                      value={form.title}
                      onChange={(e) => setForm(prev => ({ ...prev, title: e.target.value }))}
                      placeholder="Software Engineer"
                      data-testid="job-title"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="location">Location</Label>
                    <Input
                      id="location"
                      value={form.location}
                      onChange={(e) => setForm(prev => ({ ...prev, location: e.target.value }))}
                      placeholder="Remote / New York"
                      data-testid="job-location"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="type">Employment Type</Label>
                    <Select
                      value={form.employment_type}
                      onValueChange={(v) => setForm(prev => ({ ...prev, employment_type: v }))}
                    >
                      <SelectTrigger data-testid="job-type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="full-time">Full-time</SelectItem>
                        <SelectItem value="part-time">Part-time</SelectItem>
                        <SelectItem value="contract">Contract</SelectItem>
                        <SelectItem value="internship">Internship</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="salary">Salary Range</Label>
                    <Input
                      id="salary"
                      value={form.salary_range}
                      onChange={(e) => setForm(prev => ({ ...prev, salary_range: e.target.value }))}
                      placeholder="$80,000 - $120,000"
                      data-testid="job-salary"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="description">Job Description *</Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleGenerateDescription}
                      disabled={generating || !form.title}
                      className="text-indigo-600 hover:text-indigo-700"
                      data-testid="generate-desc-btn"
                    >
                      {generating ? (
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      ) : (
                        <Sparkles className="w-4 h-4 mr-1" />
                      )}
                      Generate with AI
                    </Button>
                  </div>
                  <Textarea
                    id="description"
                    value={form.description}
                    onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe the role, responsibilities, and what the candidate will work on..."
                    rows={6}
                    data-testid="job-description"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="requirements">Requirements</Label>
                  <Textarea
                    id="requirements"
                    value={form.requirements}
                    onChange={(e) => setForm(prev => ({ ...prev, requirements: e.target.value }))}
                    placeholder="List required skills, experience, education..."
                    rows={6}
                    data-testid="job-requirements"
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Playbook Tab */}
          <TabsContent value="playbook" className="space-y-6 animate-fade-in">
            {/* AI Generator */}
            <Card className="border-indigo-100 bg-gradient-to-r from-indigo-50 to-purple-50">
              <CardHeader>
                <CardTitle className="font-heading flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-indigo-500" />
                  AI Playbook Generator
                </CardTitle>
                <CardDescription>
                  Generate evaluation criteria based on the job description
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={handleGeneratePlaybook}
                  disabled={generatingPlaybook || isNew}
                  className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
                  data-testid="generate-playbook-btn"
                >
                  {generatingPlaybook ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Generate Playbook
                    </>
                  )}
                </Button>
                {isNew && (
                  <p className="text-sm text-slate-500 mt-2">Save the job first to enable playbook generation</p>
                )}
              </CardContent>
            </Card>

            {/* Playbook Categories */}
            {['character', 'requirement', 'skill'].map((category) => {
              const Icon = getCategoryIcon(category);
              const items = form.playbook?.[category] || [];
              const totalWeight = getCategoryWeight(category);
              const isValid = items.length === 0 || Math.abs(totalWeight - 100) < 0.1;

              return (
                <Card key={category} className="border-slate-100 shadow-soft">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
                        <Icon className="w-5 h-5 text-indigo-500" />
                      </div>
                      <div>
                        <CardTitle className="font-heading capitalize">{category}</CardTitle>
                        <CardDescription>
                          {category === 'character' && 'Personality traits, soft skills, cultural fit'}
                          {category === 'requirement' && 'Education, experience, certifications'}
                          {category === 'skill' && 'Technical abilities, tools, domain expertise'}
                        </CardDescription>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => addPlaybookItem(category)}
                      className="rounded-full"
                      data-testid={`add-${category}-btn`}
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Add
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {items.length === 0 ? (
                      <p className="text-sm text-slate-500 text-center py-4">No criteria defined</p>
                    ) : (
                      <>
                        {items.map((item, index) => (
                          <div key={item.id} className="p-4 rounded-xl bg-slate-50 space-y-3">
                            <div className="flex items-start gap-4">
                              <div className="flex-1 space-y-3">
                                <Input
                                  value={item.name}
                                  onChange={(e) => updatePlaybookItem(category, index, 'name', e.target.value)}
                                  placeholder="Criterion name"
                                  className="font-medium"
                                />
                                <Textarea
                                  value={item.description}
                                  onChange={(e) => updatePlaybookItem(category, index, 'description', e.target.value)}
                                  placeholder="What to evaluate"
                                  rows={2}
                                />
                                <div className="flex items-center gap-4">
                                  <Label className="text-sm text-slate-500 w-20">Weight:</Label>
                                  <Slider
                                    value={[item.weight || 0]}
                                    onValueChange={([v]) => updatePlaybookItem(category, index, 'weight', v)}
                                    max={100}
                                    step={1}
                                    className="flex-1"
                                  />
                                  <span className="text-sm font-medium w-12 text-right">{item.weight || 0}%</span>
                                </div>
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => removePlaybookItem(category, index)}
                                className="text-slate-400 hover:text-red-500"
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                        
                        <div className={`flex items-center justify-between p-3 rounded-lg ${isValid ? 'bg-green-50' : 'bg-red-50'}`}>
                          <span className={`text-sm ${isValid ? 'text-green-700' : 'text-red-700'}`}>
                            Total Weight: {totalWeight.toFixed(0)}%
                          </span>
                          <span className={`text-xs ${isValid ? 'text-green-600' : 'text-red-600'}`}>
                            {isValid ? '✓ Valid' : 'Must equal 100%'}
                          </span>
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </TabsContent>
        </Tabs>

        {/* Action Buttons */}
        <div className="flex justify-between mt-6">
          {!isNew && (
            <Button
              variant="outline"
              onClick={handleDelete}
              disabled={deleting}
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
              data-testid="delete-job-btn"
            >
              {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
              Delete Job
            </Button>
          )}
          <div className="flex-1" />
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full px-8"
            data-testid="save-job-btn"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                {isNew ? 'Create Job' : 'Save Changes'}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
