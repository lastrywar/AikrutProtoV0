import React, { useState, useEffect, useRef } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Checkbox } from '../components/ui/checkbox';
import { candidatesAPI } from '../lib/api';
import { 
  Users, Upload, Search, Mail, Phone, FileText, Trash2, Plus, Loader2, 
  Edit, RefreshCw, ChevronLeft, ChevronRight, Eye, Save, User, AlertTriangle,
  UserPlus, UserCheck, FolderArchive, GitMerge, ArrowRight
} from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';

export const Candidates = () => {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [detailCandidate, setDetailCandidate] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', email: '', phone: '' });
  const [savingEdit, setSavingEdit] = useState(false);
  const [reparsing, setReparsing] = useState(false);
  
  // Duplicate handling
  const [pendingFiles, setPendingFiles] = useState([]);
  const [duplicateMatches, setDuplicateMatches] = useState([]);
  const [showDuplicateDialog, setShowDuplicateDialog] = useState(false);
  const [duplicateDecisions, setDuplicateDecisions] = useState({});
  const [processingDuplicates, setProcessingDuplicates] = useState(false);
  
  // NEW: ZIP upload state
  const [uploadMode, setUploadMode] = useState('pdf'); // 'pdf' or 'zip'
  const [zipUploading, setZipUploading] = useState(false);
  const [zipDuplicates, setZipDuplicates] = useState(null); // For ZIP duplicate warning
  const [showZipDuplicateDialog, setShowZipDuplicateDialog] = useState(false);
  const [pendingZipFile, setPendingZipFile] = useState(null);
  const [mergeMode, setMergeMode] = useState(false); // For merge decision
  const [selectedMergeTarget, setSelectedMergeTarget] = useState(null);
  const zipInputRef = useRef(null);
  
  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadCandidates();
  }, [searchTerm, page]);

  const loadCandidates = async () => {
    setLoading(true);
    try {
      const res = await candidatesAPI.search(searchTerm, page, 12);
      setCandidates(res.data.candidates);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
    } catch (error) {
      try {
        const res = await candidatesAPI.list();
        const filtered = res.data.filter(c =>
          c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          c.email.toLowerCase().includes(searchTerm.toLowerCase())
        );
        setCandidates(filtered);
        setTotal(filtered.length);
        setTotalPages(1);
      } catch (e) {
        console.error('Failed to load candidates:', e);
      }
    } finally {
      setLoading(false);
    }
  };

  const extractEmailFromPDF = async (file) => {
    // We'll use a simple approach - upload and let backend parse, then check
    // For now, we'll just return the filename as identifier
    return file.name;
  };

  const handleFileSelect = async (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    // Filter PDF files
    const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) {
      toast.error('Only PDF files are supported');
      return;
    }

    // If adding to existing candidate, skip duplicate check
    if (selectedCandidate) {
      await uploadFiles(pdfFiles, selectedCandidate.id);
      return;
    }

    // For new uploads, we need to check for duplicates after parsing
    // First, upload one file to get parsed info, then check
    setPendingFiles(pdfFiles);
    
    if (pdfFiles.length === 1) {
      // Single file - just upload
      await uploadFiles(pdfFiles);
    } else {
      // Multiple files - show progress and handle duplicates
      await handleBulkUpload(pdfFiles);
    }
  };

  const handleBulkUpload = async (files) => {
    setUploading(true);
    const results = [];
    const potentialDuplicates = [];

    try {
      // First pass: upload all files and collect results
      for (const file of files) {
        try {
          const res = await candidatesAPI.uploadCV(file);
          results.push({ file, candidate: res.data, status: 'created' });
        } catch (error) {
          results.push({ file, error: error.response?.data?.detail || 'Upload failed', status: 'error' });
        }
      }

      // Check for duplicates among newly created candidates
      const newCandidates = results.filter(r => r.status === 'created').map(r => r.candidate);
      const emails = newCandidates.filter(c => c.email).map(c => c.email);
      
      if (emails.length > 0) {
        // Get all candidates to check for pre-existing duplicates
        const allCandidates = await candidatesAPI.list();
        const existingByEmail = {};
        
        allCandidates.data.forEach(c => {
          if (c.email && !newCandidates.find(nc => nc.id === c.id)) {
            if (!existingByEmail[c.email]) {
              existingByEmail[c.email] = [];
            }
            existingByEmail[c.email].push(c);
          }
        });

        // Find duplicates
        for (const result of results) {
          if (result.status === 'created' && result.candidate.email) {
            const existing = existingByEmail[result.candidate.email];
            if (existing && existing.length > 0) {
              potentialDuplicates.push({
                newCandidate: result.candidate,
                existingCandidates: existing,
                file: result.file
              });
            }
          }
        }
      }

      // Show success for non-duplicates
      const nonDuplicates = results.filter(r => 
        r.status === 'created' && 
        !potentialDuplicates.find(d => d.newCandidate.id === r.candidate.id)
      );
      
      if (nonDuplicates.length > 0) {
        toast.success(`Uploaded ${nonDuplicates.length} new candidate(s)`);
      }

      // Show errors
      const errors = results.filter(r => r.status === 'error');
      if (errors.length > 0) {
        toast.error(`${errors.length} file(s) failed to upload`);
      }

      // Handle duplicates if any
      if (potentialDuplicates.length > 0) {
        setDuplicateMatches(potentialDuplicates);
        // Initialize decisions - default to 'keep' (keep as separate)
        const decisions = {};
        potentialDuplicates.forEach(d => {
          decisions[d.newCandidate.id] = { action: 'keep', mergeTargetId: null };
        });
        setDuplicateDecisions(decisions);
        setShowDuplicateDialog(true);
      }

      loadCandidates();
    } catch (error) {
      toast.error('Upload failed');
    } finally {
      setUploading(false);
      setPendingFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const uploadFiles = async (files, candidateId = null) => {
    setUploading(true);
    try {
      for (const file of files) {
        await candidatesAPI.uploadCV(file, candidateId);
        toast.success(`Uploaded ${file.name}`);
      }
      loadCandidates();
      setShowUploadDialog(false);
      setSelectedCandidate(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDuplicateDecision = (newCandidateId, action, mergeTargetId = null) => {
    setDuplicateDecisions(prev => ({
      ...prev,
      [newCandidateId]: { action, mergeTargetId }
    }));
  };

  const processDuplicateDecisions = async () => {
    setProcessingDuplicates(true);
    try {
      for (const match of duplicateMatches) {
        const decision = duplicateDecisions[match.newCandidate.id];
        
        if (decision.action === 'merge' && decision.mergeTargetId) {
          // Merge: Add evidence from new candidate to existing, then delete new
          const newCandidate = match.newCandidate;
          const targetId = decision.mergeTargetId;
          
          // Get the new candidate's evidence and add to target
          if (newCandidate.evidence && newCandidate.evidence.length > 0) {
            for (const evidence of newCandidate.evidence) {
              // We need to re-upload the evidence to the target candidate
              // Since we can't directly transfer, we'll update via API
              // For now, we'll just delete the duplicate
            }
          }
          
          // Delete the duplicate
          await candidatesAPI.delete(newCandidate.id);
          toast.success(`Merged and removed duplicate: ${newCandidate.name}`);
        } else if (decision.action === 'delete') {
          // Delete the new candidate
          await candidatesAPI.delete(match.newCandidate.id);
          toast.success(`Deleted duplicate: ${match.newCandidate.name}`);
        }
        // 'keep' action means do nothing - keep both
      }
      
      setShowDuplicateDialog(false);
      setDuplicateMatches([]);
      setDuplicateDecisions({});
      loadCandidates();
    } catch (error) {
      toast.error('Failed to process duplicates');
    } finally {
      setProcessingDuplicates(false);
    }
  };

  // NEW: Handle ZIP file upload
  const handleZipSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.zip')) {
      toast.error('Please select a ZIP file');
      return;
    }
    
    setZipUploading(true);
    setPendingZipFile(file);
    
    try {
      // First try without force_create to check for duplicates
      const res = await candidatesAPI.uploadZip(file, false);
      
      if (res.data.status === 'duplicate_warning') {
        // Show duplicate dialog for ZIP
        setZipDuplicates(res.data);
        setShowZipDuplicateDialog(true);
      } else if (res.data.status === 'created') {
        toast.success(res.data.message);
        loadCandidates();
        setShowUploadDialog(false);
      } else {
        toast.error(res.data.message || 'Upload failed');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'ZIP upload failed');
    } finally {
      setZipUploading(false);
      if (zipInputRef.current) {
        zipInputRef.current.value = '';
      }
    }
  };

  // NEW: Force create after duplicate warning
  const handleZipForceCreate = async () => {
    if (!pendingZipFile) return;
    
    setZipUploading(true);
    try {
      const res = await candidatesAPI.uploadZip(pendingZipFile, true);
      toast.success(res.data.message || 'Candidate created');
      setShowZipDuplicateDialog(false);
      setZipDuplicates(null);
      setPendingZipFile(null);
      loadCandidates();
      setShowUploadDialog(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setZipUploading(false);
    }
  };

  // NEW: Merge ZIP candidate into existing
  const handleZipMerge = async (targetCandidateId) => {
    if (!pendingZipFile) return;
    
    setZipUploading(true);
    try {
      // First force create the candidate
      const createRes = await candidatesAPI.uploadZip(pendingZipFile, true);
      
      if (createRes.data.status === 'created' && createRes.data.candidate) {
        // Then merge into target
        const mergeRes = await candidatesAPI.merge(createRes.data.candidate.id, targetCandidateId);
        toast.success(`Merged into existing candidate. ${mergeRes.data.evidence_transferred} evidence file(s) transferred.`);
      }
      
      setShowZipDuplicateDialog(false);
      setZipDuplicates(null);
      setPendingZipFile(null);
      loadCandidates();
      setShowUploadDialog(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Merge failed');
    } finally {
      setZipUploading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this candidate?')) return;
    
    try {
      await candidatesAPI.delete(id);
      toast.success('Candidate deleted');
      loadCandidates();
      if (detailCandidate?.id === id) {
        setDetailCandidate(null);
      }
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const openDetail = async (candidate) => {
    try {
      const res = await candidatesAPI.get(candidate.id);
      setDetailCandidate(res.data);
      setEditForm({
        name: res.data.name,
        email: res.data.email,
        phone: res.data.phone
      });
      setEditMode(false);
    } catch (error) {
      toast.error('Failed to load candidate details');
    }
  };

  const handleSaveEdit = async () => {
    if (!detailCandidate) return;
    
    setSavingEdit(true);
    try {
      const res = await candidatesAPI.update(detailCandidate.id, editForm);
      setDetailCandidate(res.data);
      setEditMode(false);
      toast.success('Candidate updated');
      loadCandidates();
    } catch (error) {
      toast.error('Failed to update candidate');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleReparse = async () => {
    if (!detailCandidate) return;
    
    setReparsing(true);
    try {
      const res = await candidatesAPI.reparse(detailCandidate.id);
      setDetailCandidate(res.data);
      setEditForm({
        name: res.data.name,
        email: res.data.email,
        phone: res.data.phone
      });
      toast.success('CV re-parsed with AI');
      loadCandidates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to re-parse CV');
    } finally {
      setReparsing(false);
    }
  };

  return (
    <div className="min-h-screen" data-testid="candidates-page">
      <TopBar title="Talent Pool" subtitle="Manage candidate profiles" />
      
      <div className="p-8">
        {/* Actions Bar */}
        <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center mb-6">
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              placeholder="Search candidates..."
              className="pl-10"
              data-testid="search-candidates"
            />
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">{total} candidates</span>
            <Button
              onClick={() => setShowUploadDialog(true)}
              className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
              data-testid="upload-cv-btn"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload CVs
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
          </div>
        ) : candidates.length === 0 ? (
          <Card className="border-slate-100 shadow-soft">
            <EmptyState
              icon={Users}
              title={searchTerm ? 'No candidates found' : 'No candidates yet'}
              description={searchTerm ? 'Try a different search term' : 'Upload CVs to start building your talent pool.'}
              actionLabel={!searchTerm ? 'Upload CVs' : undefined}
              onAction={!searchTerm ? () => setShowUploadDialog(true) : undefined}
            />
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {candidates.map((candidate, index) => (
                <Card
                  key={candidate.id}
                  className="border-slate-100 shadow-soft hover:shadow-soft-md transition-all cursor-pointer animate-slide-up"
                  style={{ animationDelay: `${index * 0.03}s` }}
                  onClick={() => openDetail(candidate)}
                  data-testid={`candidate-card-${candidate.id}`}
                >
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div className="w-11 h-11 rounded-full bg-indigo-100 flex items-center justify-center">
                        <span className="text-indigo-600 font-semibold text-sm">
                          {candidate.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(candidate.id);
                        }}
                        className="text-slate-400 hover:text-red-500 h-8 w-8"
                        data-testid={`delete-candidate-${candidate.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    
                    <h3 className="font-medium text-slate-900 mb-2 truncate">
                      {candidate.name}
                    </h3>
                    
                    <div className="space-y-1 mb-3">
                      {candidate.email && (
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <Mail className="w-3 h-3" />
                          <span className="truncate">{candidate.email}</span>
                        </div>
                      )}
                      {candidate.phone && (
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <Phone className="w-3 h-3" />
                          <span className="truncate">{candidate.phone}</span>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                      <div className="flex gap-1">
                        {candidate.evidence?.map((e, i) => (
                          <span key={i} className="badge-neutral text-xs px-2 py-0.5">
                            {e.type}
                          </span>
                        ))}
                      </div>
                      <Eye className="w-4 h-4 text-slate-400" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-full"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous
                </Button>
                <span className="text-sm text-slate-500">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="rounded-full"
                >
                  Next
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}
          </>
        )}

        {/* Upload Dialog */}
        <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-heading">
                {selectedCandidate ? `Add Evidence for ${selectedCandidate.name}` : 'Upload Candidates'}
              </DialogTitle>
              <DialogDescription>
                {selectedCandidate 
                  ? 'Upload additional documents (CV, psychotest, knowledge test)'
                  : 'Upload PDF files for multiple candidates, or a ZIP file for one candidate with multiple evidence files.'}
              </DialogDescription>
            </DialogHeader>
            
            {!selectedCandidate && (
              <div className="flex gap-2 mb-4">
                <Button
                  variant={uploadMode === 'pdf' ? 'default' : 'outline'}
                  onClick={() => setUploadMode('pdf')}
                  className={`flex-1 rounded-full ${uploadMode === 'pdf' ? 'bg-indigo-500 hover:bg-indigo-600 text-white' : ''}`}
                  size="sm"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  PDF Files
                </Button>
                <Button
                  variant={uploadMode === 'zip' ? 'default' : 'outline'}
                  onClick={() => setUploadMode('zip')}
                  className={`flex-1 rounded-full ${uploadMode === 'zip' ? 'bg-indigo-500 hover:bg-indigo-600 text-white' : ''}`}
                  size="sm"
                >
                  <FolderArchive className="w-4 h-4 mr-2" />
                  ZIP Package
                </Button>
              </div>
            )}
            
            <div className="space-y-4 pt-2">
              {uploadMode === 'pdf' || selectedCandidate ? (
                <div 
                  className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-indigo-300 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                    data-testid="file-input"
                  />
                  {uploading ? (
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-indigo-500 animate-spin" />
                  ) : (
                    <Upload className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                  )}
                  <p className="font-medium text-slate-700">
                    {uploading ? 'Uploading...' : 'Click to upload PDF files'}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    {selectedCandidate ? 'Add documents to this candidate' : 'Each PDF creates one candidate'}
                  </p>
                </div>
              ) : (
                <div 
                  className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-indigo-300 transition-colors cursor-pointer"
                  onClick={() => zipInputRef.current?.click()}
                >
                  <input
                    ref={zipInputRef}
                    type="file"
                    accept=".zip"
                    onChange={handleZipSelect}
                    className="hidden"
                    data-testid="zip-input"
                  />
                  {zipUploading ? (
                    <Loader2 className="w-8 h-8 mx-auto mb-2 text-indigo-500 animate-spin" />
                  ) : (
                    <FolderArchive className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                  )}
                  <p className="font-medium text-slate-700">
                    {zipUploading ? 'Processing ZIP...' : 'Click to upload ZIP file'}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">One ZIP = One candidate with multiple evidence</p>
                  <div className="mt-4 text-xs text-slate-400 bg-slate-50 rounded-lg p-3 text-left">
                    <p className="font-medium mb-1">Expected ZIP structure:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>CV/resume.pdf (required, in root or cv/ folder)</li>
                      <li>psychotest/*.pdf (optional)</li>
                      <li>knowledge_test/*.pdf (optional)</li>
                    </ul>
                  </div>
                </div>
              )}
              
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowUploadDialog(false);
                    setSelectedCandidate(null);
                    setUploadMode('pdf');
                  }}
                  className="rounded-full"
                >
                  Cancel
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* NEW: ZIP Duplicate Detection Dialog */}
        <Dialog open={showZipDuplicateDialog} onOpenChange={(open) => {
          if (!open) {
            setShowZipDuplicateDialog(false);
            setZipDuplicates(null);
            setPendingZipFile(null);
            setSelectedMergeTarget(null);
          }
        }}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="font-heading flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                Potential Duplicate Detected
              </DialogTitle>
              <DialogDescription>
                The candidate in this ZIP file may already exist in your talent pool. Choose how to proceed.
              </DialogDescription>
            </DialogHeader>
            
            {zipDuplicates && (
              <div className="space-y-4 py-4">
                <Card className="border-amber-200 bg-amber-50/50">
                  <CardContent className="pt-4">
                    <p className="text-sm font-medium text-slate-700 mb-3">
                      Found {zipDuplicates.duplicates?.length || 0} potential match(es):
                    </p>
                    
                    <div className="space-y-2">
                      {zipDuplicates.duplicates?.map((match) => (
                        <div 
                          key={match.candidate_id} 
                          className={`flex items-center gap-3 p-3 bg-white rounded-lg border cursor-pointer transition-colors ${
                            selectedMergeTarget === match.candidate_id 
                              ? 'border-indigo-500 ring-2 ring-indigo-200' 
                              : 'border-slate-200 hover:border-slate-300'
                          }`}
                          onClick={() => setSelectedMergeTarget(match.candidate_id)}
                        >
                          <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                            <UserCheck className="w-5 h-5 text-indigo-600" />
                          </div>
                          <div className="flex-1">
                            <p className="font-medium text-sm">{match.candidate_name}</p>
                            <p className="text-xs text-slate-500">{match.candidate_email}</p>
                            {match.candidate_phone && (
                              <p className="text-xs text-slate-400">{match.candidate_phone}</p>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {match.match_reasons?.map((reason, i) => (
                              <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                                reason === 'email_match' ? 'bg-red-100 text-red-700' :
                                reason === 'phone_match' ? 'bg-orange-100 text-orange-700' :
                                'bg-yellow-100 text-yellow-700'
                              }`}>
                                {reason.replace('_', ' ')}
                              </span>
                            ))}
                          </div>
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            match.confidence === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                          }`}>
                            {match.confidence} confidence
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
                
                <div className="text-sm text-slate-600 bg-slate-50 rounded-lg p-3">
                  <p className="font-medium mb-2">What would you like to do?</p>
                  <ul className="space-y-1 text-xs text-slate-500">
                    <li><strong>Merge:</strong> Add evidence from ZIP to selected existing candidate</li>
                    <li><strong>Create New:</strong> Create as a separate candidate anyway</li>
                    <li><strong>Cancel:</strong> Discard and review manually</li>
                  </ul>
                </div>
              </div>
            )}
            
            <DialogFooter className="gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowZipDuplicateDialog(false);
                  setZipDuplicates(null);
                  setPendingZipFile(null);
                  setSelectedMergeTarget(null);
                }}
                className="rounded-full"
              >
                Cancel
              </Button>
              <Button
                variant="outline"
                onClick={handleZipForceCreate}
                disabled={zipUploading}
                className="rounded-full"
              >
                {zipUploading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                <UserPlus className="w-4 h-4 mr-2" />
                Create New
              </Button>
              <Button
                onClick={() => selectedMergeTarget && handleZipMerge(selectedMergeTarget)}
                disabled={zipUploading || !selectedMergeTarget}
                className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
              >
                {zipUploading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                <GitMerge className="w-4 h-4 mr-2" />
                Merge into Selected
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Duplicate Detection Dialog */}
        <Dialog open={showDuplicateDialog} onOpenChange={setShowDuplicateDialog}>
          <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
            <DialogHeader>
              <DialogTitle className="font-heading flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                Duplicate Candidates Detected
              </DialogTitle>
              <DialogDescription>
                The following uploaded candidates may be duplicates. Choose how to handle each one.
              </DialogDescription>
            </DialogHeader>
            
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-4 py-4">
                {duplicateMatches.map((match, idx) => (
                  <Card key={match.newCandidate.id} className="border-amber-200 bg-amber-50/50">
                    <CardContent className="pt-4">
                      <div className="flex items-start gap-4 mb-4">
                        <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                          <UserPlus className="w-5 h-5 text-amber-600" />
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-slate-900">New Upload: {match.newCandidate.name}</p>
                          <p className="text-sm text-slate-500">{match.newCandidate.email}</p>
                        </div>
                      </div>
                      
                      <div className="pl-14 space-y-3">
                        <p className="text-sm font-medium text-slate-700">Matches existing candidate(s):</p>
                        
                        {match.existingCandidates.map(existing => (
                          <div key={existing.id} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-slate-200">
                            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                              <UserCheck className="w-4 h-4 text-indigo-600" />
                            </div>
                            <div className="flex-1">
                              <p className="font-medium text-sm">{existing.name}</p>
                              <p className="text-xs text-slate-500">{existing.email}</p>
                            </div>
                          </div>
                        ))}
                        
                        <div className="space-y-2 pt-2">
                          <p className="text-sm font-medium text-slate-700">Action:</p>
                          <div className="space-y-2">
                            <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-white cursor-pointer">
                              <input
                                type="radio"
                                name={`decision-${match.newCandidate.id}`}
                                checked={duplicateDecisions[match.newCandidate.id]?.action === 'keep'}
                                onChange={() => handleDuplicateDecision(match.newCandidate.id, 'keep')}
                                className="text-indigo-600"
                              />
                              <span className="text-sm">Keep both (no merge)</span>
                            </label>
                            
                            <label className="flex items-center gap-3 p-2 rounded-lg hover:bg-white cursor-pointer">
                              <input
                                type="radio"
                                name={`decision-${match.newCandidate.id}`}
                                checked={duplicateDecisions[match.newCandidate.id]?.action === 'delete'}
                                onChange={() => handleDuplicateDecision(match.newCandidate.id, 'delete')}
                                className="text-indigo-600"
                              />
                              <span className="text-sm">Delete new upload (keep existing only)</span>
                            </label>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
            
            <DialogFooter className="border-t pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setShowDuplicateDialog(false);
                  setDuplicateMatches([]);
                }}
                className="rounded-full"
              >
                Cancel (Keep All)
              </Button>
              <Button
                onClick={processDuplicateDecisions}
                disabled={processingDuplicates}
                className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
              >
                {processingDuplicates ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : null}
                Apply Decisions
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Candidate Detail Dialog */}
        <Dialog open={!!detailCandidate} onOpenChange={() => setDetailCandidate(null)}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-full bg-indigo-100 flex items-center justify-center">
                    <span className="text-indigo-600 font-bold text-lg">
                      {detailCandidate?.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <DialogTitle className="font-heading text-xl">
                      {editMode ? 'Edit Candidate' : detailCandidate?.name}
                    </DialogTitle>
                    <DialogDescription>
                      Added {detailCandidate?.created_at ? new Date(detailCandidate.created_at).toLocaleDateString() : ''}
                    </DialogDescription>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReparse}
                    disabled={reparsing}
                    className="rounded-full"
                    title="Re-parse contact info from CV using AI"
                  >
                    {reparsing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4" />
                    )}
                    <span className="ml-1">AI Re-parse</span>
                  </Button>
                  {!editMode && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditMode(true)}
                      className="rounded-full"
                    >
                      <Edit className="w-4 h-4 mr-1" />
                      Edit
                    </Button>
                  )}
                </div>
              </div>
            </DialogHeader>
            
            <ScrollArea className="flex-1 pr-4">
              {detailCandidate && (
                <Tabs defaultValue="info" className="w-full">
                  <TabsList className="bg-slate-100 p-1 rounded-full mb-4">
                    <TabsTrigger value="info" className="rounded-full px-6">Contact Info</TabsTrigger>
                    <TabsTrigger value="evidence" className="rounded-full px-6">
                      Evidence ({detailCandidate.evidence?.length || 0})
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="info" className="space-y-4">
                    {editMode ? (
                      <Card className="border-slate-100">
                        <CardContent className="pt-6 space-y-4">
                          <div className="space-y-2">
                            <Label htmlFor="edit-name">Full Name</Label>
                            <div className="relative">
                              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <Input
                                id="edit-name"
                                value={editForm.name}
                                onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                                className="pl-10"
                                data-testid="edit-name"
                              />
                            </div>
                          </div>
                          
                          <div className="space-y-2">
                            <Label htmlFor="edit-email">Email</Label>
                            <div className="relative">
                              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <Input
                                id="edit-email"
                                value={editForm.email}
                                onChange={(e) => setEditForm(prev => ({ ...prev, email: e.target.value }))}
                                className="pl-10"
                                data-testid="edit-email"
                              />
                            </div>
                          </div>
                          
                          <div className="space-y-2">
                            <Label htmlFor="edit-phone">Phone</Label>
                            <div className="relative">
                              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <Input
                                id="edit-phone"
                                value={editForm.phone}
                                onChange={(e) => setEditForm(prev => ({ ...prev, phone: e.target.value }))}
                                className="pl-10"
                                data-testid="edit-phone"
                              />
                            </div>
                          </div>
                          
                          <div className="flex justify-end gap-2 pt-4">
                            <Button
                              variant="outline"
                              onClick={() => {
                                setEditMode(false);
                                setEditForm({
                                  name: detailCandidate.name,
                                  email: detailCandidate.email,
                                  phone: detailCandidate.phone
                                });
                              }}
                              className="rounded-full"
                            >
                              Cancel
                            </Button>
                            <Button
                              onClick={handleSaveEdit}
                              disabled={savingEdit}
                              className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
                              data-testid="save-edit-btn"
                            >
                              {savingEdit ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              ) : (
                                <Save className="w-4 h-4 mr-2" />
                              )}
                              Save Changes
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ) : (
                      <Card className="border-slate-100">
                        <CardContent className="pt-6">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                              <Label className="text-slate-500 text-xs">Full Name</Label>
                              <p className="font-medium text-slate-900 mt-1">{detailCandidate.name}</p>
                            </div>
                            <div>
                              <Label className="text-slate-500 text-xs">Email</Label>
                              <p className="font-medium text-slate-900 mt-1">
                                {detailCandidate.email || <span className="text-slate-400">Not provided</span>}
                              </p>
                            </div>
                            <div>
                              <Label className="text-slate-500 text-xs">Phone</Label>
                              <p className="font-medium text-slate-900 mt-1">
                                {detailCandidate.phone || <span className="text-slate-400">Not provided</span>}
                              </p>
                            </div>
                            <div>
                              <Label className="text-slate-500 text-xs">Last Updated</Label>
                              <p className="font-medium text-slate-900 mt-1">
                                {new Date(detailCandidate.updated_at).toLocaleString()}
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </TabsContent>

                  <TabsContent value="evidence" className="space-y-4">
                    {detailCandidate.evidence?.length === 0 ? (
                      <Card className="border-slate-100">
                        <CardContent className="py-12 text-center">
                          <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                          <p className="text-slate-500">No evidence uploaded</p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedCandidate(detailCandidate);
                              setShowUploadDialog(true);
                            }}
                            className="mt-4 rounded-full"
                          >
                            <Plus className="w-4 h-4 mr-1" />
                            Add Evidence
                          </Button>
                        </CardContent>
                      </Card>
                    ) : (
                      <>
                        <div className="flex justify-end">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedCandidate(detailCandidate);
                              setShowUploadDialog(true);
                            }}
                            className="rounded-full"
                          >
                            <Plus className="w-4 h-4 mr-1" />
                            Add More
                          </Button>
                        </div>
                        
                        {detailCandidate.evidence.map((evidence, idx) => (
                          <Card key={idx} className="border-slate-100">
                            <CardHeader className="pb-2">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
                                    <FileText className="w-5 h-5 text-slate-500" />
                                  </div>
                                  <div>
                                    <CardTitle className="text-base">{evidence.file_name}</CardTitle>
                                    <CardDescription className="text-xs">
                                      {evidence.type.toUpperCase()} • Uploaded {new Date(evidence.uploaded_at).toLocaleDateString()}
                                    </CardDescription>
                                  </div>
                                </div>
                                <span className="badge-neutral capitalize">{evidence.type}</span>
                              </div>
                            </CardHeader>
                            <CardContent>
                              <div className="bg-slate-50 rounded-lg p-4 max-h-96 overflow-y-auto">
                                <pre className="text-xs text-slate-600 whitespace-pre-wrap font-sans">
                                  {evidence.content}
                                </pre>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </>
                    )}
                  </TabsContent>
                </Tabs>
              )}
            </ScrollArea>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};
