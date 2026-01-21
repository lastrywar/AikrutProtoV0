import React, { useState, useEffect, useRef } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { candidatesAPI } from '../lib/api';
import { 
  Users, Upload, Search, Mail, Phone, FileText, Trash2, Plus, Loader2, 
  Edit, RefreshCw, X, ChevronLeft, ChevronRight, Eye, Save, User
} from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
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
      // Fallback to list
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

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      for (const file of files) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          toast.error(`${file.name} is not a PDF file`);
          continue;
        }
        await candidatesAPI.uploadCV(file, selectedCandidate?.id);
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
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-heading">
                {selectedCandidate ? `Add Evidence for ${selectedCandidate.name}` : 'Upload CVs'}
              </DialogTitle>
              <DialogDescription>
                {selectedCandidate 
                  ? 'Upload additional documents (CV, psychotest, knowledge test)'
                  : 'Upload PDF files to create new candidate profiles'}
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 pt-4">
              <div 
                className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-indigo-300 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  multiple
                  onChange={handleFileUpload}
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
                <p className="text-sm text-slate-500 mt-1">Or drag and drop</p>
              </div>
              
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowUploadDialog(false);
                    setSelectedCandidate(null);
                  }}
                  className="rounded-full"
                >
                  Cancel
                </Button>
              </div>
            </div>
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
