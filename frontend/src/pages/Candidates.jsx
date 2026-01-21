import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { candidatesAPI } from '../lib/api';
import { Users, Upload, Search, Mail, Phone, FileText, Trash2, Plus, Loader2 } from 'lucide-react';
import { EmptyState } from '../components/common/EmptyState';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Label } from '../components/ui/label';

export const Candidates = () => {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadCandidates();
  }, []);

  const loadCandidates = async () => {
    try {
      const res = await candidatesAPI.list();
      setCandidates(res.data);
    } catch (error) {
      console.error('Failed to load candidates:', error);
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
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const filteredCandidates = candidates.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-indigo-500">Loading...</div>
      </div>
    );
  }

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
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search candidates..."
              className="pl-10"
              data-testid="search-candidates"
            />
          </div>
          <Button
            onClick={() => setShowUploadDialog(true)}
            className="bg-indigo-500 hover:bg-indigo-600 text-white rounded-full"
            data-testid="upload-cv-btn"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload CVs
          </Button>
        </div>

        {candidates.length === 0 ? (
          <Card className="border-slate-100 shadow-soft">
            <EmptyState
              icon={Users}
              title="No candidates yet"
              description="Upload CVs to start building your talent pool."
              actionLabel="Upload CVs"
              onAction={() => setShowUploadDialog(true)}
            />
          </Card>
        ) : filteredCandidates.length === 0 ? (
          <Card className="border-slate-100 shadow-soft">
            <CardContent className="py-12 text-center">
              <p className="text-slate-500">No candidates match your search</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCandidates.map((candidate, index) => (
              <Card
                key={candidate.id}
                className="border-slate-100 shadow-soft hover:shadow-soft-md transition-all animate-slide-up"
                style={{ animationDelay: `${index * 0.05}s` }}
                data-testid={`candidate-card-${candidate.id}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center">
                      <span className="text-indigo-600 font-semibold">
                        {candidate.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(candidate.id)}
                      className="text-slate-400 hover:text-red-500"
                      data-testid={`delete-candidate-${candidate.id}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                  
                  <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
                    {candidate.name}
                  </h3>
                  
                  <div className="space-y-2 mb-4">
                    {candidate.email && (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Mail className="w-4 h-4" />
                        <span className="truncate">{candidate.email}</span>
                      </div>
                    )}
                    {candidate.phone && (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Phone className="w-4 h-4" />
                        {candidate.phone}
                      </div>
                    )}
                  </div>
                  
                  {/* Evidence Summary */}
                  <div className="pt-4 border-t border-slate-100">
                    <p className="text-xs text-slate-500 mb-2">Evidence:</p>
                    <div className="flex flex-wrap gap-2">
                      {candidate.evidence?.map((e, i) => (
                        <span key={i} className="badge-neutral text-xs">
                          <FileText className="w-3 h-3 mr-1 inline" />
                          {e.type}
                        </span>
                      ))}
                      {(!candidate.evidence || candidate.evidence.length === 0) && (
                        <span className="text-xs text-slate-400">No evidence uploaded</span>
                      )}
                    </div>
                  </div>
                  
                  {/* Add Evidence Button */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedCandidate(candidate);
                      setShowUploadDialog(true);
                    }}
                    className="w-full mt-4 text-indigo-600"
                    data-testid={`add-evidence-${candidate.id}`}
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    Add Evidence
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
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
      </div>
    </div>
  );
};
