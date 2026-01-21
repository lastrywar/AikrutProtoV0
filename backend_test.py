import requests
import sys
import json
from datetime import datetime
import uuid

class TalentAITester:
    def __init__(self, base_url="https://hire-helper-ai-2.preview.emergentagent.com"):
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