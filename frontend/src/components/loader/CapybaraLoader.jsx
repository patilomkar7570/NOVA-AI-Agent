/*
From Uiverse.io by Novaxlo - https://uiverse.io/Novaxlo/kind-snail-5
MIT License, Copyright (c) Novaxlo (Novaxlo)
*/

import React from 'react';
import './CapybaraLoader.css';

export default function CapybaraLoader() {
  return (
    <div className="capybaraloader-wrapper" aria-label="Loading response...">
      <div className="capybaraloader">
        <div className="capybara">
          <div className="capyhead">
            <div className="capyear">
              <div className="capyear2"></div>
            </div>
            <div className="capyear"></div>
            <div className="capymouth">
              <div className="capylips"></div>
              <div className="capylips"></div>
            </div>
            <div className="capyeye"></div>
            <div className="capyeye"></div>
          </div>
          <div className="capyleg"></div>
          <div className="capyleg2"></div>
          <div className="capyleg2"></div>
          <div className="capy"></div>
        </div>
        <div className="loader">
          <div className="loaderline"></div>
        </div>
      </div>
    </div>
  );
}
