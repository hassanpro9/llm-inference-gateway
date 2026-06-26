import http from 'k6/http';
import { sleep, check } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  // Gemini 2.5 Flash free tier: 5 RPM hard limit.
  // 1 VU × 1 req per 15s = 4 RPM — safely under the cap.
  // For a paid key, increase vus to 5 and reduce sleep to 3s.
  vus: 1,
  duration: '90s',
  thresholds: {
    errors: ['rate<0.05'],
    http_req_duration: ['p(95)<15000'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

const PROMPTS = [
  'What is Kubernetes in one sentence?',
  'Explain Docker containers briefly.',
  'What does a Prometheus metric scrape endpoint do?',
  'Describe the purpose of a Horizontal Pod Autoscaler.',
  'What is the difference between a Deployment and a StatefulSet?',
];

export default function () {
  const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];

  const payload = JSON.stringify({
    model: 'gemini-2.5-flash',
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 128,
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: '15s',
  };

  const res = http.post(`${BASE_URL}/v1/chat`, payload, params);

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'response has choices': (r) => {
      try {
        return JSON.parse(r.body).choices !== undefined;
      } catch {
        return false;
      }
    },
    'response time < 10s': (r) => r.timings.duration < 10000,
  });

  errorRate.add(!success);

  // 15s sleep keeps us at ~4 RPM — under the 5 RPM free tier hard limit.
  sleep(15);
}
