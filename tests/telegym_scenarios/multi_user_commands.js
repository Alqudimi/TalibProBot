import tg from 'k6/x/telegym';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    concurrent_users: {
      executor: 'constant-vus',
      vus: 5,
      duration: '10s',
    },
  },
  thresholds: {
    checks: ['rate>0.95'],
    http_req_failed: ['rate<0.05'],
  },
};

export default function () {
  const u = tg.newUser(0);
  const commands = ['/help', '/edu', '/daily', '/support', '/privacy', '/cancel'];
  const command = commands[__ITER % commands.length];
  u.send(command);
  const reply = u.awaitText('.+', 10);
  check(reply, {
    [`${command} returned a reply`]: (m) => m !== null,
    'reply latency under 2s': (m) => m && m.latencyMs < 2000,
  });
  sleep(0.1);
}
