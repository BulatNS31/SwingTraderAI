import React from 'react';

const TimeFrameSwitcher: React.FC = () => {
  const timeframes = ['H1', 'H4', 'D1'];
  return (
    <select>
      {timeframes.map((tf) => (
        <option key={tf} value={tf}>
          {tf}
        </option>
      ))}
    </select>
  );
};

export default TimeFrameSwitcher;
