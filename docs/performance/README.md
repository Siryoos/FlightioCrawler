# Performance Metrics

To verify Core Web Vitals and Lighthouse scores, run:

```bash
npm run build && npx lighthouse http://localhost:3000 --preset=desktop --output html --output-path ./lighthouse.html
```

Bundle analysis can be generated with:

```bash
ANALYZE=true npm run build
```
