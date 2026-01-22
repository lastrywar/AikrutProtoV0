import React, { useState, useEffect, useCallback } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Slider } from '../components/ui/slider';
import { Checkbox } from '../components/ui/checkbox';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { jobsAPI, candidatesAPI, analysisAPI } from '../lib/api';
import { 
  BarChart3, Play, Loader2, ChevronDown, ChevronUp, Users, Target, Wrench, 
  Search, CheckCircle, XCircle, AlertCircle, ChevronLeft, ChevronRight,
  Star, TrendingUp, TrendingDown, FileText, Heart, Trash2, UserX
} from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';
import { ScoreRing, ScoreBadge } from '../components/common/ScoreRing';
import { toast } from 'sonner';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';

export const Analysis = () => {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [selectedJobData, setSelectedJobData] = useState(null);
  
  // Candidate selection with search/pagination
  const [candidateSearch, setCandidateSearch] = useState('');
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidateData, setCandidateData] = useState({ candidates: [], total: 0, pages: 0 });
  const [selectedCandidates, setSelectedCandidates] = useState([]);
  const [candidatesMap, setCandidatesMap] = useState({});
  
  // Results
  const [results, setResults] = useState([]);
  const [minScore, setMinScore] = useState(0);
  const [selectedResults, setSelectedResults] = useState([]);
  
  // Loading states
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState({ current: 0, total: 0, status: '', candidateName: '' });
  
  // Detail view
  const [expandedResult, setExpandedResult] = useState(null);
  const [detailModalResult, setDetailModalResult] = useState(null);

  useEffect(() => {
    loadJobs();
    loadAllCandidates();
  }, []);

  useEffect(() => {
    loadCandidates();
  }, [candidateSearch, candidatePage]);

  useEffect(() => {
    if (selectedJob) {
      loadResults();
      loadJobData();
    }
  }, [selectedJob, minScore]);

  const loadJobs = async () => {
    try {
      const res = await jobsAPI.list();
      setJobs(res.data);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadJobData = async () => {
    if (!selectedJob) return;
    try {
      const res = await jobsAPI.get(selectedJob);
      setSelectedJobData(res.data);
    } catch (error) {
      console.error('Failed to load job:', error);
    }
  };

  const loadAllCandidates = async () => {
    try {
      const res = await candidatesAPI.list();
      const map = {};
      res.data.forEach(c => { map[c.id] = c; });
      setCandidatesMap(map);
    } catch (error) {
      console.error('Failed to load all candidates:', error);
    }
  };

  const loadCandidates = useCallback(async () => {
    try {
      const res = await candidatesAPI.search(candidateSearch, candidatePage, 15);
      setCandidateData(res.data);
    } catch (error) {
      try {
        const res = await candidatesAPI.list();
        setCandidateData({ candidates: res.data, total: res.data.length, pages: 1 });
      } catch (e) {
        console.error('Failed to load candidates:', e);
      }
    }
  }, [candidateSearch, candidatePage]);

  const loadResults = async () => {
    try {
      const res = await analysisAPI.getForJob(selectedJob, minScore || null);
      setResults(res.data);
      setSelectedResults([]);
    } catch (error) {
      console.error('Failed to load results:', error);
    }
  };

  const toggleCandidate = (id) => {
    setSelectedCandidates(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const selectAllVisible = () => {
    const visibleIds = candidateData.candidates.map(c => c.id);
    const allSelected = visibleIds.every(id => selectedCandidates.includes(id));
    
    if (allSelected) {
      setSelectedCandidates(prev => prev.filter(id => !visibleIds.includes(id)));
    } else {
      setSelectedCandidates(prev => [...new Set([...prev, ...visibleIds])]);
    }
  };

  const toggleResultSelection = (id) => {
    setSelectedResults(prev =>
      prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]
    );
  };

  const selectAllResults = () => {
    if (selectedResults.length === results.length) {
      setSelectedResults([]);
    } else {
      setSelectedResults(results.map(r => r.id));
    }
  };

  const handleBulkDeleteResults = async () => {
    if (selectedResults.length === 0) return;
    
    if (!window.confirm(`Delete ${selectedResults.length} analysis result(s)? This cannot be undone.`)) return;
    
    setDeleting(true);
    try {
      await analysisAPI.bulkDelete(selectedResults);
      toast.success(`Deleted ${selectedResults.length} result(s)`);
      setSelectedResults([]);
      loadResults();
    } catch (error) {
      toast.error('Failed to delete results');
    } finally {
      setDeleting(false);
    }
  };

  const runAnalysis = async () => {
    if (!selectedJob) {
      toast.error('Select a job first');
      return;
    }
    if (selectedCandidates.length === 0) {
      toast.error('Select at least one candidate');
      return;
    }

    const job = jobs.find(j => j.id === selectedJob);
    if (!job?.playbook) {
      toast.error('The selected job needs a playbook. Generate one in Job settings.');
      return;
    }

    setAnalyzing(true);
    setAnalysisProgress({ current: 0, total: selectedCandidates.length, status: 'starting', candidateName: '' });

    try {
      const response = await analysisAPI.runStream(selectedJob, selectedCandidates);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.startsWith('data: '));

        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'progress') {
              setAnalysisProgress({
                current: data.current,
                total: data.total,
                status: data.status,
                candidateName: data.candidate_name || '',
                message: data.message
              });
            } else if (data.type === 'result') {
              setResults(prev => {
                const exists = prev.find(r => r.id === data.analysis.id);
                if (exists) return prev;
                return [...prev, data.analysis].sort((a, b) => b.final_score - a.final_score);
              });
              setAnalysisProgress(prev => ({
                ...prev,
                current: data.current,
                status: 'completed'
              }));
            } else if (data.type === 'error') {
              toast.error(`Failed to analyze: ${data.error}`);
              setAnalysisProgress(prev => ({
                ...prev,
                current: data.current,
                status: 'error'
              }));
            } else if (data.type === 'complete') {
              toast.success(`Analysis complete! ${data.total} candidate(s) processed.`);
            }
          } catch (e) {
            console.error('Parse error:', e);
          }
        }
      }
    } catch (error) {
      toast.error(error.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
      setSelectedCandidates([]);
      loadResults();
      loadAllCandidates();
    }
  };

  const getCandidateName = (result) => {
    // First try to get from candidatesMap (live data)
    const candidate = candidatesMap[result.candidate_id];
    if (candidate) {
      return candidate.name;
    }
    // Fall back to stored candidate_name
    if (result.candidate_name) {
      return `[Deleted] ${result.candidate_name}`;
    }
    return '[Deleted] Unknown';
  };

  const isCandidateDeleted = (result) => {
    return !candidatesMap[result.candidate_id];
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'character': return Users;
      case 'requirement': return Target;
      case 'skill': return Wrench;
      default: return BarChart3;
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    if (score >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" data-testid="analysis-page">
      <TopBar title="Job Fit Analysis" subtitle="AI-powered candidate evaluation" />
      
      <div className="p-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel - Configuration */}
          <div className="space-y-6">
            {/* Job Selection */}
            <Card className="border-slate-100 shadow-soft">
              <CardHeader className="pb-3">
                <CardTitle className="font-heading text-lg">Select Job</CardTitle>
              </CardHeader>
              <CardContent>
                <Select value={selectedJob} onValueChange={setSelectedJob}>
                  <SelectTrigger data-testid="select-job">
                    <SelectValue placeholder="Choose a job position" />
                  </SelectTrigger>
                  <SelectContent>
                    {jobs.map(job => (
                      <SelectItem key={job.id} value={job.id}>
                        <div className="flex items-center gap-2">
                          <span>{job.title}</span>
                          {!job.playbook && (
                            <span className="text-xs text-amber-600">(no playbook)</span>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            {/* Candidate Selection with Search */}
            <Card className="border-slate-100 shadow-soft">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="font-heading text-lg">Select Candidates</CardTitle>
                  <span className="text-sm text-slate-500">
                    {selectedCandidates.length} selected
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <Input
                    value={candidateSearch}
                    onChange={(e) => {
                      setCandidateSearch(e.target.value);
                      setCandidatePage(1);
                    }}
                    placeholder="Search candidates..."
                    className="pl-9"
                    data-testid="candidate-search"
                  />
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={selectAllVisible}
                  className="text-indigo-600 w-full justify-start"
                  data-testid="select-all-btn"
                >
                  {candidateData.candidates.every(c => selectedCandidates.includes(c.id)) 
                    ? 'Deselect All Visible' 
                    : 'Select All Visible'}
                </Button>

                <ScrollArea className="h-[280px]">
                  {candidateData.candidates.length === 0 ? (
                    <p className="text-sm text-slate-500 text-center py-4">No candidates found</p>
                  ) : (
                    <div className="space-y-1">
                      {candidateData.candidates.map(candidate => (
                        <label
                          key={candidate.id}
                          className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                            selectedCandidates.includes(candidate.id)
                              ? 'bg-indigo-50 border border-indigo-200'
                              : 'hover:bg-slate-50'
                          }`}
                        >
                          <Checkbox
                            checked={selectedCandidates.includes(candidate.id)}
                            onCheckedChange={() => toggleCandidate(candidate.id)}
                            data-testid={`select-candidate-${candidate.id}`}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm text-slate-900 truncate">{candidate.name}</p>
                            <p className="text-xs text-slate-500 truncate">{candidate.email}</p>
                          </div>
                          <span className="text-xs text-slate-400 flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            {candidate.evidence?.length || 0}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </ScrollArea>

                {candidateData.pages > 1 && (
                  <div className="flex items-center justify-between pt-2 border-t">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCandidatePage(p => Math.max(1, p - 1))}
                      disabled={candidatePage === 1}
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <span className="text-sm text-slate-500">
                      Page {candidatePage} of {candidateData.pages}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCandidatePage(p => Math.min(candidateData.pages, p + 1))}
                      disabled={candidatePage === candidateData.pages}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                )}

                <p className="text-xs text-slate-400 text-center">
                  Total: {candidateData.total} candidates
                </p>
              </CardContent>
            </Card>

            {/* Analysis Progress */}
            {analyzing && (
              <Card className="border-indigo-200 bg-indigo-50">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-indigo-700">Analyzing...</span>
                      <span className="text-sm text-indigo-600">
                        {analysisProgress.current} / {analysisProgress.total}
                      </span>
                    </div>
                    <Progress 
                      value={(analysisProgress.current / analysisProgress.total) * 100} 
                      className="h-2"
                    />
                    {analysisProgress.candidateName && (
                      <p className="text-xs text-indigo-600 flex items-center gap-2">
                        {analysisProgress.status === 'analyzing' && (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        )}
                        {analysisProgress.status === 'completed' && (
                          <CheckCircle className="w-3 h-3" />
                        )}
                        {analysisProgress.candidateName}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Run Analysis Button */}
            <Button
              onClick={runAnalysis}
              disabled={analyzing || !selectedJob || selectedCandidates.length === 0}
              className="w-full bg-indigo-500 hover:bg-indigo-600 text-white rounded-full py-6"
              data-testid="run-analysis-btn"
            >
              {analyzing ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Analyzing {analysisProgress.current}/{analysisProgress.total}...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5 mr-2" />
                  Run Analysis ({selectedCandidates.length})
                </>
              )}
            </Button>

            {/* Shortlist Filter */}
            <Card className="border-slate-100 shadow-soft">
              <CardHeader className="pb-3">
                <CardTitle className="font-heading text-lg">Shortlist Filter</CardTitle>
                <CardDescription>Minimum score threshold</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Slider
                    value={[minScore]}
                    onValueChange={([v]) => setMinScore(v)}
                    max={100}
                    step={5}
                    data-testid="min-score-slider"
                  />
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">Min Score:</span>
                    <span className="font-medium">{minScore}%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Panel - Results */}
          <div className="lg:col-span-2">
            <Card className="border-slate-100 shadow-soft h-full">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="font-heading flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-indigo-500" />
                      Analysis Results
                    </CardTitle>
                    <CardDescription>
                      {results.length > 0 
                        ? `${results.length} candidate(s) scored${minScore > 0 ? ` (≥${minScore}%)` : ''}`
                        : 'Select candidates and run analysis'}
                    </CardDescription>
                  </div>
                  
                  {/* Bulk Actions */}
                  {results.length > 0 && (
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={selectAllResults}
                        className="text-slate-600"
                      >
                        {selectedResults.length === results.length ? 'Deselect All' : 'Select All'}
                      </Button>
                      {selectedResults.length > 0 && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleBulkDeleteResults}
                          disabled={deleting}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          data-testid="bulk-delete-btn"
                        >
                          {deleting ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4 mr-1" />
                          )}
                          Delete ({selectedResults.length})
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {results.length === 0 ? (
                  <EmptyState
                    icon={BarChart3}
                    title="No results yet"
                    description="Select a job and candidates, then run the analysis to see AI-powered scoring."
                  />
                ) : (
                  <div className="space-y-4">
                    {results.sort((a, b) => b.final_score - a.final_score).map((result, index) => {
                      const isDeleted = isCandidateDeleted(result);
                      
                      return (
                        <Collapsible
                          key={result.id}
                          open={expandedResult === result.id}
                          onOpenChange={() => setExpandedResult(expandedResult === result.id ? null : result.id)}
                        >
                          <div
                            className={`rounded-xl border transition-all ${
                              expandedResult === result.id 
                                ? 'border-indigo-200 bg-indigo-50/50' 
                                : isDeleted 
                                  ? 'border-red-100 bg-red-50/30'
                                  : 'border-slate-100 hover:border-slate-200'
                            }`}
                          >
                            <CollapsibleTrigger asChild>
                              <div
                                className="p-4 cursor-pointer"
                                data-testid={`result-${result.id}`}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-4">
                                    {/* Selection Checkbox */}
                                    <Checkbox
                                      checked={selectedResults.includes(result.id)}
                                      onCheckedChange={(e) => {
                                        e.stopPropagation?.();
                                        toggleResultSelection(result.id);
                                      }}
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                    
                                    <div className="font-semibold text-lg text-slate-400 w-8">
                                      #{index + 1}
                                    </div>
                                    <ScoreRing score={result.final_score} size={56} strokeWidth={5} />
                                    <div>
                                      <p className="font-heading font-semibold text-slate-900 flex items-center gap-2">
                                        {isDeleted && <UserX className="w-4 h-4 text-red-500" />}
                                        {getCandidateName(result)}
                                      </p>
                                      <div className="flex items-center gap-2 mt-1">
                                        <ScoreBadge score={result.final_score} />
                                        {result.final_score >= minScore && minScore > 0 && (
                                          <span className="badge-success text-xs">
                                            <CheckCircle className="w-3 h-3 mr-1 inline" />
                                            Shortlisted
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setDetailModalResult(result);
                                      }}
                                      className="text-indigo-600"
                                    >
                                      View Details
                                    </Button>
                                    {expandedResult === result.id ? (
                                      <ChevronUp className="w-5 h-5 text-slate-400" />
                                    ) : (
                                      <ChevronDown className="w-5 h-5 text-slate-400" />
                                    )}
                                  </div>
                                </div>
                              </div>
                            </CollapsibleTrigger>
                            
                            <CollapsibleContent>
                              <div className="px-4 pb-4 pt-0 space-y-4 border-t border-slate-100">
                                {result.overall_reasoning && (
                                  <div className="pt-4">
                                    <p className="text-sm font-medium text-slate-700 mb-2">Summary</p>
                                    <p className="text-sm text-slate-600 bg-white p-3 rounded-lg">
                                      {result.overall_reasoning}
                                    </p>
                                  </div>
                                )}

                                <div className="grid grid-cols-2 gap-4">
                                  {result.strengths?.length > 0 && (
                                    <div className="bg-green-50 rounded-lg p-3">
                                      <p className="text-xs font-medium text-green-700 mb-2 flex items-center gap-1">
                                        <TrendingUp className="w-3 h-3" /> Strengths
                                      </p>
                                      <ul className="text-xs text-green-700 space-y-1">
                                        {result.strengths.map((s, i) => (
                                          <li key={i}>• {s}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  {result.gaps?.length > 0 && (
                                    <div className="bg-amber-50 rounded-lg p-3">
                                      <p className="text-xs font-medium text-amber-700 mb-2 flex items-center gap-1">
                                        <TrendingDown className="w-3 h-3" /> Gaps
                                      </p>
                                      <ul className="text-xs text-amber-700 space-y-1">
                                        {result.gaps.map((g, i) => (
                                          <li key={i}>• {g}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                                
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                  {result.category_scores?.map(cat => {
                                    const Icon = getCategoryIcon(cat.category);
                                    return (
                                      <div key={cat.category} className="bg-white rounded-lg p-3 border border-slate-100">
                                        <div className="flex items-center justify-between mb-2">
                                          <div className="flex items-center gap-2">
                                            <Icon className="w-4 h-4 text-indigo-500" />
                                            <span className="font-medium capitalize text-sm">{cat.category}</span>
                                          </div>
                                          <span className={`font-bold ${getScoreColor(cat.score)}`}>
                                            {Math.round(cat.score)}
                                          </span>
                                        </div>
                                        <Progress value={cat.score} className="h-1.5" />
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            </CollapsibleContent>
                          </div>
                        </Collapsible>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      <Dialog open={!!detailModalResult} onOpenChange={() => setDetailModalResult(null)}>
        <DialogContent className="max-w-4xl h-[85vh] flex flex-col">
          <DialogHeader className="flex-shrink-0">
            <DialogTitle className="font-heading flex items-center gap-3">
              <ScoreRing score={detailModalResult?.final_score || 0} size={48} strokeWidth={5} />
              <div>
                <span className="flex items-center gap-2">
                  {detailModalResult && isCandidateDeleted(detailModalResult) && (
                    <UserX className="w-5 h-5 text-red-500" />
                  )}
                  {detailModalResult && getCandidateName(detailModalResult)}
                </span>
                <p className="text-sm font-normal text-slate-500">
                  Detailed Analysis Report
                </p>
              </div>
            </DialogTitle>
          </DialogHeader>
          
          <div className="flex-1 overflow-y-auto pr-2">
            {detailModalResult && (
              <Tabs defaultValue="overview" className="w-full">
                <TabsList className="bg-slate-100 p-1 rounded-full mb-4">
                  <TabsTrigger value="overview" className="rounded-full px-4">Overview</TabsTrigger>
                  <TabsTrigger value="character" className="rounded-full px-4">Character</TabsTrigger>
                  <TabsTrigger value="requirement" className="rounded-full px-4">Requirements</TabsTrigger>
                  <TabsTrigger value="skill" className="rounded-full px-4">Skills</TabsTrigger>
                  <TabsTrigger value="values" className="rounded-full px-4">Values</TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-4">
                  <div className="grid grid-cols-4 gap-4">
                    <div className="bg-slate-50 rounded-xl p-4 text-center">
                      <p className="text-xs text-slate-500 mb-1">Final Score</p>
                      <p className={`text-2xl font-bold ${getScoreColor(detailModalResult.final_score)}`}>
                        {Math.round(detailModalResult.final_score)}
                      </p>
                    </div>
                    {detailModalResult.category_scores?.map(cat => (
                      <div key={cat.category} className="bg-slate-50 rounded-xl p-4 text-center">
                        <p className="text-xs text-slate-500 mb-1 capitalize">{cat.category}</p>
                        <p className={`text-2xl font-bold ${getScoreColor(cat.score)}`}>
                          {Math.round(cat.score)}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="bg-slate-50 rounded-xl p-4">
                    <p className="font-medium text-slate-700 mb-2">Overall Assessment</p>
                    <p className="text-slate-600">{detailModalResult.overall_reasoning}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-green-50 rounded-xl p-4">
                      <p className="font-medium text-green-700 mb-2 flex items-center gap-2">
                        <Star className="w-4 h-4" /> Key Strengths
                      </p>
                      <ul className="space-y-2">
                        {detailModalResult.strengths?.map((s, i) => (
                          <li key={i} className="text-sm text-green-700 flex items-start gap-2">
                            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                            {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="bg-amber-50 rounded-xl p-4">
                      <p className="font-medium text-amber-700 mb-2 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" /> Areas for Improvement
                      </p>
                      <ul className="space-y-2">
                        {detailModalResult.gaps?.map((g, i) => (
                          <li key={i} className="text-sm text-amber-700 flex items-start gap-2">
                            <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                            {g}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </TabsContent>

                {/* Category Tabs */}
                {['character', 'requirement', 'skill'].map(category => {
                  const catData = detailModalResult.category_scores?.find(c => c.category === category);
                  const Icon = getCategoryIcon(category);
                  const playbookItems = selectedJobData?.playbook?.[category] || [];
                  
                  return (
                    <TabsContent key={category} value={category} className="space-y-4">
                      <div className="flex items-center justify-between bg-slate-50 rounded-xl p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                            <Icon className="w-5 h-5 text-indigo-600" />
                          </div>
                          <div>
                            <p className="font-medium capitalize">{category}</p>
                            <p className="text-sm text-slate-500">
                              {playbookItems.length} criteria evaluated
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className={`text-3xl font-bold ${getScoreColor(catData?.score || 0)}`}>
                            {Math.round(catData?.score || 0)}
                          </p>
                          <p className="text-xs text-slate-500">Category Score</p>
                        </div>
                      </div>

                      <div className="space-y-3">
                        {catData?.breakdown?.map((item, idx) => {
                          const playbookItem = playbookItems.find(p => p.id === item.item_id) || {};
                          return (
                            <div key={item.item_id || idx} className="bg-white border border-slate-100 rounded-xl p-4">
                              <div className="flex items-start justify-between mb-2">
                                <div className="flex-1">
                                  <p className="font-medium text-slate-900">
                                    {item.item_name || playbookItem.name || `Criterion ${idx + 1}`}
                                  </p>
                                  {playbookItem.description && (
                                    <p className="text-xs text-slate-500 mt-1">{playbookItem.description}</p>
                                  )}
                                </div>
                                <div className="text-right ml-4">
                                  <p className={`text-xl font-bold ${getScoreColor(item.raw_score)}`}>
                                    {Math.round(item.raw_score)}
                                  </p>
                                  <p className="text-xs text-slate-500">Weight: {item.weight}%</p>
                                </div>
                              </div>
                              <Progress value={item.raw_score} className="h-1.5 mb-2" />
                              <p className="text-sm text-slate-600 bg-slate-50 p-2 rounded-lg">
                                {item.reasoning || 'No reasoning provided'}
                              </p>
                            </div>
                          );
                        })}

                        {playbookItems
                          .filter(p => !catData?.breakdown?.find(b => b.item_id === p.id))
                          .map(item => (
                            <div key={item.id} className="bg-slate-50 border border-slate-200 border-dashed rounded-xl p-4">
                              <div className="flex items-center justify-between">
                                <div>
                                  <p className="font-medium text-slate-500">{item.name}</p>
                                  <p className="text-xs text-slate-400">{item.description}</p>
                                </div>
                                <span className="text-xs text-slate-400">Not evaluated</span>
                              </div>
                            </div>
                          ))
                        }
                      </div>
                    </TabsContent>
                  );
                })}

                {/* Company Values Tab */}
                <TabsContent value="values" className="space-y-4">
                  {detailModalResult.company_values_alignment ? (
                    <>
                      <div className="flex items-center justify-between bg-slate-50 rounded-xl p-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-pink-100 flex items-center justify-center">
                            <Heart className="w-5 h-5 text-pink-600" />
                          </div>
                          <div>
                            <p className="font-medium">Company Values Alignment</p>
                            <p className="text-sm text-slate-500">Cultural fit assessment</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className={`text-3xl font-bold ${getScoreColor(detailModalResult.company_values_alignment.score || 0)}`}>
                            {Math.round(detailModalResult.company_values_alignment.score || 0)}
                          </p>
                          <p className="text-xs text-slate-500">Alignment Score</p>
                        </div>
                      </div>

                      {detailModalResult.company_values_alignment.notes && (
                        <div className="bg-white border border-slate-100 rounded-xl p-4">
                          <p className="text-sm text-slate-600">
                            {detailModalResult.company_values_alignment.notes}
                          </p>
                        </div>
                      )}

                      {detailModalResult.company_values_alignment.breakdown?.map((value, idx) => (
                        <div key={idx} className="bg-white border border-slate-100 rounded-xl p-4">
                          <div className="flex items-start justify-between mb-2">
                            <p className="font-medium text-slate-900">{value.value_name}</p>
                            <p className={`text-xl font-bold ${getScoreColor(value.score)}`}>
                              {Math.round(value.score)}
                            </p>
                          </div>
                          <Progress value={value.score} className="h-1.5 mb-2" />
                          <p className="text-sm text-slate-600 bg-slate-50 p-2 rounded-lg">
                            {value.reasoning}
                          </p>
                        </div>
                      ))}
                    </>
                  ) : (
                    <div className="text-center py-8 text-slate-500">
                      <Heart className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                      <p>No company values alignment data available</p>
                      <p className="text-sm">Configure company values in Company Settings to enable this.</p>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
