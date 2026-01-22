import requests
import sys
import json
import re
from datetime import datetime
import uuid

class TalentAITester:
    def __init__(self, base_url="https://aikrut-v0-deploy.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.company_id = None
        self.job_id = None
        self.candidate_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name} - PASSED")
        else:
            print(f"❌ {test_name} - FAILED: {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if files:
                # Remove Content-Type for file uploads
                headers.pop('Content-Type', None)
                
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, data=data, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            
            if success:
                self.log_result(name, True)
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"
                self.log_result(name, False, error_msg)
                return False, {}

        except Exception as e:
            self.log_result(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_user_registration(self):
        """Test user registration"""
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        test_name = "Test User"
        test_password = "testpass123"
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "email": test_email,
                "name": test_name,
                "password": test_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.test_email = test_email
            self.test_password = test_password
            return True
        return False

    def test_user_login(self):
        """Test user login"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={
                "email": self.test_email,
                "password": self.test_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            return True
        return False

    def test_get_user_profile(self):
        """Test get current user profile"""
        success, response = self.run_test(
            "Get User Profile",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        return success

    def test_create_company(self):
        """Test company creation"""
        success, response = self.run_test(
            "Create Company",
            "POST",
            "company",
            200,
            data={
                "name": "Test Company Inc",
                "description": "A test company for CV screening",
                "industry": "Technology",
                "website": "https://testcompany.com",
                "values": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Innovation",
                        "description": "We value creative problem solving",
                        "weight": 50
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Teamwork",
                        "description": "Collaboration is key to our success",
                        "weight": 50
                    }
                ]
            }
        )
        
        if success and 'id' in response:
            self.company_id = response['id']
            return True
        return False

    def test_get_company(self):
        """Test get company details"""
        success, response = self.run_test(
            "Get Company",
            "GET",
            "company",
            200
        )
        return success

    def test_create_job(self):
        """Test job creation"""
        success, response = self.run_test(
            "Create Job",
            "POST",
            "jobs",
            200,
            data={
                "title": "Senior Software Engineer",
                "description": "We are looking for an experienced software engineer to join our team.",
                "requirements": "5+ years of experience in Python, React, and MongoDB",
                "location": "Remote",
                "employment_type": "full-time",
                "salary_range": "$80,000 - $120,000"
            }
        )
        
        if success and 'id' in response:
            self.job_id = response['id']
            return True
        return False

    def test_list_jobs(self):
        """Test list jobs"""
        success, response = self.run_test(
            "List Jobs",
            "GET",
            "jobs",
            200
        )
        return success

    def test_get_job(self):
        """Test get specific job"""
        if not self.job_id:
            self.log_result("Get Job", False, "No job ID available")
            return False
            
        success, response = self.run_test(
            "Get Job",
            "GET",
            f"jobs/{self.job_id}",
            200
        )
        return success

    def test_create_candidate(self):
        """Test candidate creation"""
        success, response = self.run_test(
            "Create Candidate",
            "POST",
            "candidates",
            200,
            data={
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890"
            }
        )
        
        if success and 'id' in response:
            self.candidate_id = response['id']
            return True
        return False

    def test_list_candidates(self):
        """Test list candidates"""
        success, response = self.run_test(
            "List Candidates",
            "GET",
            "candidates",
            200
        )
        return success

    def test_get_settings(self):
        """Test get settings"""
        success, response = self.run_test(
            "Get Settings",
            "GET",
            "settings",
            200
        )
        return success

    def test_update_settings(self):
        """Test update settings"""
        success, response = self.run_test(
            "Update Settings",
            "PUT",
            "settings",
            200,
            data={
                "model_name": "openai/gpt-4o-mini",
                "language": "en"
            }
        )
        return success

    def test_recent_activity(self):
        """Test recent activity"""
        success, response = self.run_test(
            "Recent Activity",
            "GET",
            "dashboard/recent-activity",
            200
        )
        return success

    # NEW CANDIDATE MANAGEMENT ENDPOINTS TESTS
    def test_detect_duplicates_no_match(self):
        """Test detect duplicates with no matches"""
        success, response = self.run_test(
            "Detect Duplicates - No Match",
            "POST",
            "candidates/detect-duplicates",
            200,
            data={
                "email": "unique.email@example.com",
                "phone": "+9999999999",
                "name": "Unique Person"
            }
        )
        
        if success and 'has_duplicates' in response:
            if response['has_duplicates'] == False and len(response.get('matches', [])) == 0:
                return True
            else:
                self.log_result("Detect Duplicates - No Match", False, f"Expected no duplicates but got: {response}")
                return False
        return success

    def test_detect_duplicates_email_match(self):
        """Test detect duplicates with email match"""
        # First create a candidate to match against
        if not self.candidate_id:
            self.log_result("Detect Duplicates - Email Match", False, "No candidate created yet")
            return False
            
        success, response = self.run_test(
            "Detect Duplicates - Email Match",
            "POST",
            "candidates/detect-duplicates",
            200,
            data={
                "email": "john.doe@example.com",  # Same as created candidate
                "phone": "+9876543210",
                "name": "Different Name"
            }
        )
        
        if success and 'has_duplicates' in response:
            if response['has_duplicates'] == True and len(response.get('matches', [])) > 0:
                match = response['matches'][0]
                if 'email_match' in match.get('match_reasons', []):
                    return True
                else:
                    self.log_result("Detect Duplicates - Email Match", False, f"Expected email_match in reasons but got: {match.get('match_reasons', [])}")
                    return False
            else:
                self.log_result("Detect Duplicates - Email Match", False, f"Expected duplicates but got: {response}")
                return False
        return success

    def test_detect_duplicates_phone_match(self):
        """Test detect duplicates with phone match"""
        if not self.candidate_id:
            self.log_result("Detect Duplicates - Phone Match", False, "No candidate created yet")
            return False
            
        success, response = self.run_test(
            "Detect Duplicates - Phone Match",
            "POST",
            "candidates/detect-duplicates",
            200,
            data={
                "email": "different.email@example.com",
                "phone": "1234567890",  # Same as created candidate (normalized)
                "name": "Different Name"
            }
        )
        
        if success and 'has_duplicates' in response:
            if response['has_duplicates'] == True and len(response.get('matches', [])) > 0:
                match = response['matches'][0]
                if 'phone_match' in match.get('match_reasons', []):
                    return True
                else:
                    self.log_result("Detect Duplicates - Phone Match", False, f"Expected phone_match in reasons but got: {match.get('match_reasons', [])}")
                    return False
            else:
                self.log_result("Detect Duplicates - Phone Match", False, f"Expected duplicates but got: {response}")
                return False
        return success

    def test_upload_zip_error_handling(self):
        """Test upload ZIP without actual ZIP file (error handling)"""
        # Test with non-ZIP file to verify error handling
        success, response = self.run_test(
            "Upload ZIP - Error Handling",
            "POST",
            "candidates/upload-zip",
            400,  # Expecting 400 error for non-ZIP
            data={"force_create": "false"},
            files={"file": ("test.txt", "This is not a ZIP file", "text/plain")}
        )
        return success

    def test_merge_candidates(self):
        """Test merge candidates endpoint"""
        # Create a second candidate to merge
        success, response = self.run_test(
            "Create Second Candidate for Merge",
            "POST",
            "candidates",
            200,
            data={
                "name": "Jane Smith",
                "email": "jane.smith@example.com",
                "phone": "+9876543210"
            }
        )
        
        if not success or 'id' not in response:
            self.log_result("Merge Candidates", False, "Failed to create second candidate")
            return False
            
        second_candidate_id = response['id']
        
        # Now test merge
        success, response = self.run_test(
            "Merge Candidates",
            "POST",
            "candidates/merge",
            200,
            data={
                "source_candidate_id": second_candidate_id,
                "target_candidate_id": self.candidate_id
            }
        )
        
        if success and 'message' in response and 'evidence_transferred' in response:
            if response['message'] == "Candidates merged successfully":
                return True
            else:
                self.log_result("Merge Candidates", False, f"Unexpected message: {response.get('message')}")
                return False
        return success

    def test_merge_logs(self):
        """Test get merge logs endpoint"""
        success, response = self.run_test(
            "Get Merge Logs",
            "GET",
            "candidates/merge-logs",
            200
        )
        
        if success and isinstance(response, list):
            # Should have at least one log entry from the merge test
            if len(response) >= 1:
                log_entry = response[0]
                required_fields = ['action', 'source_id', 'target_id', 'merged_at', 'merged_by']
                if all(field in log_entry for field in required_fields):
                    return True
                else:
                    missing_fields = [field for field in required_fields if field not in log_entry]
                    self.log_result("Get Merge Logs", False, f"Missing fields in log entry: {missing_fields}")
                    return False
            else:
                self.log_result("Get Merge Logs", False, "No merge logs found after merge operation")
                return False
        return success

    # UPDATED UPLOAD-CV ENDPOINT TESTS
    def create_sample_pdf_content(self):
        """Create a simple PDF-like content for testing"""
        return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(John Smith) Tj
0 -20 Td
(john.smith@email.com) Tj
0 -20 Td
(+1-555-123-4567) Tj
0 -20 Td
(Software Engineer with 5 years experience) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""

    def test_upload_cv_first_time(self):
        """Test 1: Upload CV - First time (no duplicates)"""
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - First Time",
            "POST",
            "candidates/upload-cv",
            200,
            data={},
            files={"file": ("john_smith_cv.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            # Check response structure
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'created':
                    self.first_upload_candidate_id = response['candidate']['id']
                    print(f"   Created candidate ID: {self.first_upload_candidate_id}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    print(f"   Evidence types: {response['evidence_types']}")
                    return True
                else:
                    self.log_result("Upload CV - First Time", False, f"Expected status 'created', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - First Time", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_duplicate_detection(self):
        """Test 2: Upload same CV again (duplicate detection)"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Upload CV - Duplicate Detection", False, "First upload test must run first")
            return False
            
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - Duplicate Detection",
            "POST",
            "candidates/upload-cv",
            200,
            data={},
            files={"file": ("john_smith_cv_duplicate.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'duplicates', 'extracted_info', 'evidence_preview']
            if all(field in response for field in expected_fields):
                if response['status'] == 'duplicate_warning':
                    duplicates = response['duplicates']
                    if len(duplicates) > 0:
                        print(f"   Found {len(duplicates)} duplicate(s)")
                        print(f"   Extracted info: {response['extracted_info']}")
                        print(f"   Evidence preview: {response['evidence_preview']}")
                        return True
                    else:
                        self.log_result("Upload CV - Duplicate Detection", False, "No duplicates found when expected")
                        return False
                else:
                    self.log_result("Upload CV - Duplicate Detection", False, f"Expected status 'duplicate_warning', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - Duplicate Detection", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_force_create(self):
        """Test 3: Force create despite duplicate"""
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - Force Create",
            "POST",
            "candidates/upload-cv",
            200,
            data={"force_create": "true"},
            files={"file": ("john_smith_cv_force.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'created':
                    self.force_created_candidate_id = response['candidate']['id']
                    print(f"   Force created candidate ID: {self.force_created_candidate_id}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    return True
                else:
                    self.log_result("Upload CV - Force Create", False, f"Expected status 'created', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - Force Create", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_merge_into_existing(self):
        """Test 4: Merge into existing candidate"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Upload CV - Merge Into Existing", False, "First upload test must run first")
            return False
            
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - Merge Into Existing",
            "POST",
            "candidates/upload-cv",
            200,
            data={"merge_target_id": self.first_upload_candidate_id},
            files={"file": ("john_smith_additional.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'merged':
                    print(f"   Merged into candidate ID: {response['candidate']['id']}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    print(f"   Evidence types: {response['evidence_types']}")
                    return True
                else:
                    self.log_result("Upload CV - Merge Into Existing", False, f"Expected status 'merged', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - Merge Into Existing", False, f"Missing fields: {missing}")
                return False
        return success

    def test_upload_cv_to_existing_candidate(self):
        """Test 5: Upload to existing candidate (candidate_id)"""
        if not hasattr(self, 'first_upload_candidate_id'):
            self.log_result("Upload CV - To Existing Candidate", False, "First upload test must run first")
            return False
            
        pdf_content = self.create_sample_pdf_content()
        
        success, response = self.run_test(
            "Upload CV - To Existing Candidate",
            "POST",
            "candidates/upload-cv",
            200,
            data={"candidate_id": self.first_upload_candidate_id},
            files={"file": ("john_smith_update.pdf", pdf_content, "application/pdf")}
        )
        
        if success:
            expected_fields = ['status', 'candidate', 'evidence_added', 'evidence_types']
            if all(field in response for field in expected_fields):
                if response['status'] == 'updated':
                    print(f"   Updated candidate ID: {response['candidate']['id']}")
                    print(f"   Evidence added: {response['evidence_added']}")
                    print(f"   Evidence types: {response['evidence_types']}")
                    return True
                else:
                    self.log_result("Upload CV - To Existing Candidate", False, f"Expected status 'updated', got '{response['status']}'")
                    return False
            else:
                missing = [f for f in expected_fields if f not in response]
                self.log_result("Upload CV - To Existing Candidate", False, f"Missing fields: {missing}")
                return False
        return success

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting TalentAI Backend API Tests")
        print("=" * 50)
        
        # Authentication Tests
        print("\n📝 Authentication Tests")
        if not self.test_user_registration():
            print("❌ Registration failed, stopping tests")
            return False
            
        if not self.test_user_login():
            print("❌ Login failed, stopping tests")
            return False
            
        self.test_get_user_profile()
        
        # Dashboard Tests
        print("\n📊 Dashboard Tests")
        self.test_dashboard_stats()
        self.test_recent_activity()
        
        # Company Tests
        print("\n🏢 Company Tests")
        self.test_create_company()
        self.test_get_company()
        
        # Job Tests
        print("\n💼 Job Tests")
        self.test_create_job()
        self.test_list_jobs()
        self.test_get_job()
        
        # Candidate Tests
        print("\n👥 Candidate Tests")
        self.test_create_candidate()
        self.test_list_candidates()
        
        # NEW Candidate Management Tests
        print("\n🔍 NEW Candidate Management Tests")
        self.test_detect_duplicates_no_match()
        self.test_detect_duplicates_email_match()
        self.test_detect_duplicates_phone_match()
        self.test_upload_zip_error_handling()
        self.test_merge_candidates()
        self.test_merge_logs()
        
        # UPDATED Upload-CV Endpoint Tests
        print("\n📄 UPDATED Upload-CV Endpoint Tests")
        self.test_upload_cv_first_time()
        self.test_upload_cv_duplicate_detection()
        self.test_upload_cv_force_create()
        self.test_upload_cv_merge_into_existing()
        self.test_upload_cv_to_existing_candidate()
        
        # Settings Tests
        print("\n⚙️ Settings Tests")
        self.test_get_settings()
        self.test_update_settings()
        
        # Print Results
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("❌ Some tests failed. Check the details above.")
            failed_tests = [r for r in self.test_results if not r['success']]
            print("\nFailed Tests:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
            return False

def main():
    tester = TalentAITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())