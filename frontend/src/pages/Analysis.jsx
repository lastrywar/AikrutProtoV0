import React, { useState, useEffect } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Slider } from '../components/ui/slider';
import { Checkbox } from '../components/ui/checkbox';
import { jobsAPI, candidatesAPI, analysisAPI } from '../lib/api';
import { BarChart3, Play, Loader2, ChevronDown, ChevronUp, Users, Target, Wrench } from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';
import { ScoreRing, ScoreBadge } from '../components/common/ScoreRing';
import { toast } from 'sonner';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '../components/ui/collapsible';

export const Analysis = () => {
  const [jobs, setJobs] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [selectedCandidates, setSelectedCandidates] = useState([]);
  const [results, setResults] = useState([]);
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [expandedResult, setExpandedResult] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedJob) {
      loadResults();
    }
  }, [selectedJob, minScore]);

  const loadData = async () => {
    try {
      const [jobsRes, candidatesRes] = await Promise.all([
        jobsAPI.list(),
        candidatesAPI.list()
      ]);
      setJobs(jobsRes.data);
      setCandidates(candidatesRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadResults = async () => {
    try {
      const res = await analysisAPI.getForJob(selectedJob, minScore || null);
      setResults(res.data);
    } catch (error) {
      console.error('Failed to load results:', error);
    }
  };

  const toggleCandidate = (id) => {
    setSelectedCandidates(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedCandidates.length === candidates.length) {
      setSelectedCandidates([]);
    } else {
      setSelectedCandidates(candidates.map(c => c.id));
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
    try {
      const res = await analysisAPI.runBatch(selectedJob, selectedCandidates);
      setResults(res.data);
      toast.success(`Analyzed ${res.data.length} candidate(s)`);
      setSelectedCandidates([]);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const getCandidateName = (candidateId) => {
    const candidate = candidates.find(c => c.id === candidateId);
    return candidate?.name || 'Unknown';
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'character': return Users;
      case 'requirement': return Target;
      case 'skill': return Wrench;
      default: return BarChart3;
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
    <div className="min-h-screen" data-testid="analysis-page">
      <TopBar title="Job Fit Analysis" subtitle="AI-powered candidate evaluation" />
      
      <div className="p-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel - Configuration */}
          <div className="space-y-6">
            {/* Job Selection */}
            <Card className="border-slate-100 shadow-soft">
              <CardHeader>
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

            {/* Candidate Selection */}
            <Card className="border-slate-100 shadow-soft">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="font-heading text-lg">Select Candidates</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={selectAll}
                  className="text-indigo-600"
                  data-testid="select-all-btn"
                >
                  {selectedCandidates.length === candidates.length ? 'Deselect All' : 'Select All'}
                </Button>
              </CardHeader>
              <CardContent>
                {candidates.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-4">No candidates available</p>
                ) : (
                  <div className="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
                    {candidates.map(candidate => (
                      <label
                        key={candidate.id}
                        className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 cursor-pointer"
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
                        <span className="text-xs text-slate-400">
                          {candidate.evidence?.length || 0} docs
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

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
                  Analyzing...
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
              <CardHeader>
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
                <CardTitle className="font-heading flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-indigo-500" />
                  Analysis Results
                </CardTitle>
                <CardDescription>
                  {results.length > 0 
                    ? `${results.length} candidate(s) scored`
                    : 'Select candidates and run analysis'}
                </CardDescription>
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
                    {results.sort((a, b) => b.final_score - a.final_score).map((result, index) => (
                      <Collapsible
                        key={result.id}
                        open={expandedResult === result.id}
                        onOpenChange={() => setExpandedResult(expandedResult === result.id ? null : result.id)}
                      >
                        <div
                          className={`rounded-xl border transition-all ${
                            expandedResult === result.id ? 'border-indigo-200 bg-indigo-50/50' : 'border-slate-100 hover:border-slate-200'
                          }`}
                        >
                          <CollapsibleTrigger asChild>
                            <div
                              className="p-4 cursor-pointer flex items-center justify-between"
                              data-testid={`result-${result.id}`}
                            >
                              <div className="flex items-center gap-4">
                                <div className="font-semibold text-lg text-slate-400 w-8">
                                  #{index + 1}
                                </div>
                                <ScoreRing score={result.final_score} size={56} strokeWidth={5} />
                                <div>
                                  <p className="font-heading font-semibold text-slate-900">
                                    {getCandidateName(result.candidate_id)}
                                  </p>
                                  <ScoreBadge score={result.final_score} />
                                </div>
                              </div>
                              {expandedResult === result.id ? (
                                <ChevronUp className="w-5 h-5 text-slate-400" />
                              ) : (
                                <ChevronDown className="w-5 h-5 text-slate-400" />
                              )}
                            </div>
                          </CollapsibleTrigger>
                          
                          <CollapsibleContent>
                            <div className="px-4 pb-4 pt-0 space-y-4 border-t border-slate-100 mt-0">
                              {/* Overall Reasoning */}
                              {result.overall_reasoning && (
                                <div className="pt-4">
                                  <p className="text-sm font-medium text-slate-700 mb-2">Overall Assessment</p>
                                  <p className="text-sm text-slate-600 bg-white p-3 rounded-lg">
                                    {result.overall_reasoning}
                                  </p>
                                </div>
                              )}
                              
                              {/* Category Scores */}
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                                {result.category_scores?.map(cat => {
                                  const Icon = getCategoryIcon(cat.category);
                                  return (
                                    <div key={cat.category} className="bg-white rounded-lg p-4">
                                      <div className="flex items-center gap-2 mb-3">
                                        <Icon className="w-4 h-4 text-indigo-500" />
                                        <span className="font-medium capitalize text-sm">{cat.category}</span>
                                        <ScoreBadge score={cat.score} showLabel={false} />
                                      </div>
                                      <div className="space-y-2">
                                        {cat.breakdown?.slice(0, 3).map(item => (
                                          <div key={item.item_id} className="text-xs">
                                            <div className="flex justify-between mb-1">
                                              <span className="text-slate-600 truncate">{item.item_name}</span>
                                              <span className="font-medium">{Math.round(item.raw_score)}</span>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>

                              {/* Company Values Alignment */}
                              {result.company_values_alignment && (
                                <div className="bg-white rounded-lg p-4">
                                  <p className="text-sm font-medium text-slate-700 mb-2">Company Values Alignment</p>
                                  <div className="flex items-center gap-3">
                                    <ScoreRing score={result.company_values_alignment.score || 0} size={40} strokeWidth={4} />
                                    <p className="text-sm text-slate-600">
                                      {result.company_values_alignment.notes || 'No notes available'}
                                    </p>
                                  </div>
                                </div>
                              )}
                            </div>
                          </CollapsibleContent>
                        </div>
                      </Collapsible>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};
