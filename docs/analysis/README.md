# Website Analysis

This directory contains analysis notes for target travel websites used by the crawler.

## Available Analysis

### FlyToday
- **URL Pattern**: `https://www.flytoday.ir/flight/search?departure=thr,1&arrival=syz,1&departureDate=2025-06-10&adt=1&chd=0&inf=0&cabin=1&isDomestic=true&isAnyWhere=false`
- **Technical Implementation**: Uses XHR for search results
- **Persian Support**: RTL layouts with Persian numerals
- **Status**: Active analysis available

## Adding New Analysis

When analyzing new websites, document:
- UI/UX patterns and user flow
- Persian text handling and RTL support
- Technical implementation details (XHR, APIs, etc.)
- Unique features or challenges
- Production URL patterns

## Purpose

These analyses help:
- Understand target website patterns
- Improve crawler implementation
- Track changes in website structure
- Optimize Persian language handling
- Enhance frontend development insights
